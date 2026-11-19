"""Módulo de DTOs (Data Transfer Objects) y discretización física para RAIN."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("RAIN.DTOs")

# Constantes físicas para la conversión flujo -> luminosidad isotrópica
_C_KM_S: float = 299_792.458
_MPC_TO_CM: float = 3.085677581491367e24

VALID_STATES: Dict[str, List[str]] = {
    "Galaxia_Anfitriona": ["Espiral", "Eliptica", "Irregular"],
    "Tipo_Transitorio": ["SN_Ia", "SN_II", "AGN", "Variable_Estelar"],
    "Ubicacion_Galactica": ["Nuclear", "Brazo_Espiral", "Halo"],
    "Extincion_Polvo": ["Baja", "Moderada", "Severa"],
    "Temperatura_Intrinseca": ["Alta", "Media", "Baja"],
    "Luminosidad_Pico": ["Muy_Alta", "Moderada", "Baja"],
    "Velocidad_Expansion": ["Muy_Alta", "Moderada", "Baja_Nula"],
    "Color_Observado": ["Azul", "Neutro", "Rojo"],
    "Magnitud_Aparente": ["Brillante", "Intermedia", "Debil"],
    "Emision_RayosX": ["Intensa", "Debil", "Nula"],
    "Anchura_Lineas": ["Anchas", "Estrechas", "Ausentes"],
    "Forma_Curva_Luz": ["Decaimiento_Rapido", "Meseta", "Estocastica"],
}

OBSERVABLE_NODES: List[str] = [
    "Galaxia_Anfitriona",
    "Ubicacion_Galactica",
    "Color_Observado",
    "Magnitud_Aparente",
    "Emision_RayosX",
    "Anchura_Lineas",
    "Forma_Curva_Luz",
]


class ValidationError(ValueError):
    """Excepción para valores nulos, no finitos, fuera de rango o estados discretos inválidos."""


@dataclass(frozen=True)
class DiscretizationConfig:
    """Parámetros configurables de discretización física (por umbrales o percentiles).

    Por defecto reproduce exactamente los umbrales de la Tabla 2 del documento de diseño.
    """

    r_kpc: Tuple[float, float] = (1.0, 15.0)
    g_minus_r: Tuple[float, float] = (0.0, 0.5)
    m_v: Tuple[float, float] = (17.0, 19.5)
    l_x: Tuple[float, float] = (1e39, 1e42)
    fwhm_kms: float = 3000.0
    x_ray_flux: Tuple[float, float] = (1e-14, 1e-11)
    dust_extinction_ebv: Tuple[float, float] = (0.10, 0.50)
    use_luminosity_from_redshift: bool = True
    hubble_constant_km_s_mpc: float = 70.0

    @classmethod
    def from_json(cls, config_path: Union[str, Path]) -> "DiscretizationConfig":
        """Carga la configuración de umbrales desde un fichero JSON."""
        path = Path(config_path)
        if not path.exists():
            logger.warning("Fichero '%s' no encontrado; usando umbrales por defecto (Tabla 2).", path)
            return cls()

        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        th = data.get("thresholds", {})
        return cls(
            r_kpc=tuple(th.get("r_kpc", cls.r_kpc)),  # type: ignore[arg-type]
            g_minus_r=tuple(th.get("g_minus_r", cls.g_minus_r)),  # type: ignore[arg-type]
            m_v=tuple(th.get("m_v", cls.m_v)),  # type: ignore[arg-type]
            l_x=tuple(th.get("l_x", cls.l_x)),  # type: ignore[arg-type]
            fwhm_kms=float(th.get("fwhm_kms", cls.fwhm_kms)),
            x_ray_flux=tuple(th.get("x_ray_flux", cls.x_ray_flux)),  # type: ignore[arg-type]
            dust_extinction_ebv=tuple(th.get("dust_extinction_ebv", cls.dust_extinction_ebv)),  # type: ignore[arg-type]
            use_luminosity_from_redshift=bool(
                data.get("use_luminosity_from_redshift", cls.use_luminosity_from_redshift)
            ),
            hubble_constant_km_s_mpc=float(
                data.get("hubble_constant_km_s_mpc", cls.hubble_constant_km_s_mpc)
            ),
        )

    @classmethod
    def from_dataframe_percentiles(
        cls,
        df: pd.DataFrame,
        quantiles: Tuple[float, float] = (0.33, 0.67),
        base_config: Optional["DiscretizationConfig"] = None,
    ) -> "DiscretizationConfig":
        """Calcula límites dinámicos basados en percentiles empíricos del dataset.

        Para cada variable continua $X$ presente con valores finitos, particiona su dominio
        en tres regímenes usando los cuantiles $(q_1, q_2)$ con $0 < q_1 < q_2 < 1$.
        """
        q_low, q_high = quantiles
        if not (0.0 < q_low < q_high < 1.0):
            raise ValidationError(f"Cuantiles inválidos: {quantiles}. Se requiere 0 < q1 < q2 < 1.")

        base = base_config or cls()

        def _pair(col: str, fallback: Tuple[float, float]) -> Tuple[float, float]:
            if col not in df.columns:
                return fallback
            series = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if len(series) < 3:
                return fallback
            lo, hi = float(series.quantile(q_low)), float(series.quantile(q_high))
            return (lo, hi) if lo < hi else fallback

        def _single(col: str, fallback: float, q: float = 0.67) -> float:
            if col not in df.columns:
                return fallback
            series = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            series = series[series > 0]
            return float(series.quantile(q)) if len(series) >= 3 else fallback

        return cls(
            r_kpc=_pair("r_kpc", base.r_kpc),
            g_minus_r=_pair("g_minus_r", base.g_minus_r),
            m_v=_pair("apparent_magnitude" if "apparent_magnitude" in df.columns else "m_v", base.m_v),
            l_x=_pair("l_x", base.l_x),
            fwhm_kms=_single(
                "velocity_km_s" if "velocity_km_s" in df.columns else "fwhm_kms",
                base.fwhm_kms,
                q=q_high,
            ),
            x_ray_flux=_pair("x_ray_flux", base.x_ray_flux),
            dust_extinction_ebv=_pair("dust_extinction_ebv", base.dust_extinction_ebv),
            use_luminosity_from_redshift=base.use_luminosity_from_redshift,
            hubble_constant_km_s_mpc=base.hubble_constant_km_s_mpc,
        )


def _validate_finite_float(
    value: Any,
    name: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    """Convierte a float y valida finitud y dominio físico."""
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Valor no numérico en '{name}': {value!r}") from exc

    if math.isnan(numeric) or math.isinf(numeric):
        raise ValidationError(f"Valor nulo o no finito detectado en '{name}': {value!r}")
    if min_value is not None and numeric < min_value:
        raise ValidationError(f"'{name}'={numeric} está por debajo del límite físico ({min_value}).")
    if max_value is not None and numeric > max_value:
        raise ValidationError(f"'{name}'={numeric} supera el límite físico ({max_value}).")
    return numeric


def discretize_dust_ebv(ebv: float, config: Optional[DiscretizationConfig] = None) -> str:
    """Mapea la extinción interestelar $E(B-V)$ [mag] al espacio discreto de Extincion_Polvo."""
    cfg = config or DiscretizationConfig()
    val = _validate_finite_float(ebv, "dust_extinction_ebv", min_value=0.0, max_value=10.0)
    lo, hi = cfg.dust_extinction_ebv
    if val < lo:
        return "Baja"
    if val > hi:
        return "Severa"
    return "Moderada"


def flux_to_xray_luminosity(flux_cgs: float, redshift_z: float, h0: float = 70.0) -> float:
    """Estima la luminosidad isotrópica en rayos X $L_X$ [erg/s] a bajo/moderado redshift.

    Aproximación de distancia de luminosidad en ley de Hubble:
    $$d_L(z) \\approx \\frac{c \\cdot z}{H_0} (1 + z), \\qquad L_X = 4 \\pi d_L(z)^2 F_X$$
    """
    d_mpc = (_C_KM_S * redshift_z / h0) * (1.0 + redshift_z)
    d_cm = d_mpc * _MPC_TO_CM
    return 4.0 * math.pi * (d_cm ** 2) * flux_cgs


@dataclass
class AstronomicalAlert:
    """DTO de entrada concordante con Figura 1 de la arquitectura."""

    galaxia: Optional[str] = None
    ubicacion: Optional[str] = None
    color: Optional[str] = None
    magnitud: Optional[str] = None
    rayos_x: Optional[str] = None
    anchura_lineas: Optional[str] = None
    curva_luz: Optional[str] = None

    @classmethod
    def from_continuous(
        cls,
        raw: Dict[str, Any],
        config: Optional[DiscretizationConfig] = None,
    ) -> "AstronomicalAlert":
        """Discretiza mediciones físicas continuas mediante límites parametrizables.

        Soporta tanto las claves de la Tabla 2 (`r_kpc`, `g_minus_r`, `m_v`, `l_x`, `fwhm_kms`)
        como las columnas de datasets reales (`apparent_magnitude`, `redshift_z`,
        `velocity_km_s`, `x_ray_flux`, `dust_extinction_ebv`).
        """
        cfg = config or DiscretizationConfig()

        galaxia = raw.get("galaxia")
        ubicacion = raw.get("ubicacion")
        if raw.get("r_kpc") is not None:
            r = _validate_finite_float(raw["r_kpc"], "r_kpc", min_value=0.0)
            r_lo, r_hi = cfg.r_kpc
            ubicacion = "Nuclear" if r < r_lo else ("Halo" if r > r_hi else "Brazo_Espiral")

        color = raw.get("color")
        if raw.get("g_minus_r") is not None:
            gr = _validate_finite_float(raw["g_minus_r"], "g_minus_r", min_value=-5.0, max_value=10.0)
            gr_lo, gr_hi = cfg.g_minus_r
            color = "Azul" if gr < gr_lo else ("Rojo" if gr > gr_hi else "Neutro")

        magnitud = raw.get("magnitud")
        mv_raw = raw.get("m_v") if raw.get("m_v") is not None else raw.get("apparent_magnitude")
        if mv_raw is not None:
            mv = _validate_finite_float(mv_raw, "apparent_magnitude", min_value=-30.0, max_value=40.0)
            mv_lo, mv_hi = cfg.m_v
            magnitud = "Brillante" if mv < mv_lo else ("Debil" if mv > mv_hi else "Intermedia")

        rayos_x = raw.get("rayos_x")
        if raw.get("l_x") is not None:
            lx = _validate_finite_float(raw["l_x"], "l_x", min_value=0.0)
            lx_lo, lx_hi = cfg.l_x
            rayos_x = "Intensa" if lx > lx_hi else ("Debil" if lx >= lx_lo else "Nula")
        elif raw.get("x_ray_flux") is not None:
            fx = _validate_finite_float(raw["x_ray_flux"], "x_ray_flux", min_value=0.0)
            z_raw = raw.get("redshift_z")
            if cfg.use_luminosity_from_redshift and z_raw is not None:
                z_val = _validate_finite_float(z_raw, "redshift_z", min_value=0.0, max_value=20.0)
                if z_val > 0.0:
                    lx = flux_to_xray_luminosity(fx, z_val, h0=cfg.hubble_constant_km_s_mpc)
                    lx_lo, lx_hi = cfg.l_x
                    rayos_x = "Intensa" if lx > lx_hi else ("Debil" if lx >= lx_lo else "Nula")
                else:
                    fx_lo, fx_hi = cfg.x_ray_flux
                    rayos_x = "Intensa" if fx > fx_hi else ("Debil" if fx >= fx_lo else "Nula")
            else:
                fx_lo, fx_hi = cfg.x_ray_flux
                rayos_x = "Intensa" if fx > fx_hi else ("Debil" if fx >= fx_lo else "Nula")

        anchura_lineas = raw.get("anchura_lineas")
        vel_raw = raw.get("fwhm_kms") if raw.get("fwhm_kms") is not None else raw.get("velocity_km_s")
        if vel_raw is not None:
            fwhm = _validate_finite_float(vel_raw, "velocity_km_s", min_value=0.0, max_value=_C_KM_S)
            anchura_lineas = (
                "Ausentes" if fwhm <= 0.0 else ("Anchas" if fwhm > cfg.fwhm_kms else "Estrechas")
            )

        curva_luz = raw.get("curva_luz")

        alerta = cls(
            galaxia=galaxia,
            ubicacion=ubicacion,
            color=color,
            magnitud=magnitud,
            rayos_x=rayos_x,
            anchura_lineas=anchura_lineas,
            curva_luz=curva_luz,
        )
        alerta.validar_estados()
        return alerta

    @classmethod
    def from_continuous_data(
        cls,
        raw: Dict[str, Any],
        config: Optional[DiscretizationConfig] = None,
    ) -> "AstronomicalAlert":
        """Alias mantenido por compatibilidad con el texto descriptivo de la Sección 1."""
        return cls.from_continuous(raw, config=config)

    def to_evidence_dict(self) -> Dict[str, str]:
        """Convierte los atributos observados al diccionario de evidencias para pgmpy."""
        mapping = {
            "Galaxia_Anfitriona": self.galaxia,
            "Ubicacion_Galactica": self.ubicacion,
            "Color_Observado": self.color,
            "Magnitud_Aparente": self.magnitud,
            "Emision_RayosX": self.rayos_x,
            "Anchura_Lineas": self.anchura_lineas,
            "Forma_Curva_Luz": self.curva_luz,
        }
        return {k: v for k, v in mapping.items() if v is not None}

    def obtener_faltantes(self) -> List[str]:
        """Retorna las variables observables que aún no han sido medidas."""
        evidencias = self.to_evidence_dict()
        return [nodo for nodo in OBSERVABLE_NODES if nodo not in evidencias]

    def validar_estados(self) -> bool:
        """Valida que los estados introducidos pertenezcan al espacio discreto."""
        for var, estado in self.to_evidence_dict().items():
            if estado not in VALID_STATES[var]:
                raise ValidationError(
                    f"Estado '{estado}' inválido para '{var}'. Permitidos: {VALID_STATES[var]}"
                )
        return True


@dataclass
class DiagnosisResult:
    """DTO de salida concordante con los atributos de la Figura 1."""

    prob_transitorio: Dict[str, float]
    fisica_latente: Dict[str, Dict[str, float]]
    ganancia_info_ig: Dict[str, float] = field(default_factory=dict)
    clase_predicha: str = ""
    confianza: float = 0.0
    entropia_shannon: float = 0.0

    def __post_init__(self) -> None:
        if self.prob_transitorio and not self.clase_predicha:
            self.clase_predicha, self.confianza = max(
                self.prob_transitorio.items(), key=lambda item: item[1]
            )

    def resumen_fisica_latente(self) -> str:
        """Formatea el estado más probable de cada variable física del Nivel 3."""
        partes = []
        for var, dist in self.fisica_latente.items():
            estado_top, prob_top = max(dist.items(), key=lambda x: x[1])
            partes.append(f"{var}: {estado_top} ({prob_top * 100:.1f}%)")
        return " | ".join(partes)