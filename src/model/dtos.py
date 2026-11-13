# src/model/dtos.py
from dataclasses import dataclass, field
from typing import Dict, Optional, List

VALID_STATES = {
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

OBSERVABLE_NODES = [
    "Galaxia_Anfitriona",
    "Ubicacion_Galactica",
    "Color_Observado",
    "Magnitud_Aparente",
    "Emision_RayosX",
    "Anchura_Lineas",
    "Forma_Curva_Luz",
]


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
    def from_continuous(cls, raw: Dict[str, float | str | None]) -> "AstronomicalAlert":
        """Discretiza mediciones físicas continuas según los umbrales de la Tabla 2."""
        galaxia = raw.get("galaxia")

        ubicacion = raw.get("ubicacion")
        if "r_kpc" in raw and raw["r_kpc"] is not None:
            r = float(raw["r_kpc"])
            ubicacion = "Nuclear" if r < 1.0 else ("Halo" if r > 15.0 else "Brazo_Espiral")

        color = raw.get("color")
        if "g_minus_r" in raw and raw["g_minus_r"] is not None:
            gr = float(raw["g_minus_r"])
            color = "Azul" if gr < 0.0 else ("Rojo" if gr > 0.5 else "Neutro")

        magnitud = raw.get("magnitud")
        if "m_v" in raw and raw["m_v"] is not None:
            mv = float(raw["m_v"])
            magnitud = "Brillante" if mv < 17.0 else ("Debil" if mv > 19.5 else "Intermedia")

        rayos_x = raw.get("rayos_x")
        if "l_x" in raw and raw["l_x"] is not None:
            lx = float(raw["l_x"])
            rayos_x = "Intensa" if lx > 1e42 else ("Debil" if lx >= 1e39 else "Nula")

        anchura_lineas = raw.get("anchura_lineas")
        if "fwhm_kms" in raw and raw["fwhm_kms"] is not None:
            fwhm = float(raw["fwhm_kms"])
            anchura_lineas = "Ausentes" if fwhm <= 0 else ("Anchas" if fwhm > 3000.0 else "Estrechas")

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
    def from_continuous_data(cls, raw: Dict[str, float | str | None]) -> "AstronomicalAlert":
        """Alias mantenido por compatibilidad con el texto descriptivo de la Sección 1."""
        return cls.from_continuous(raw)

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
                raise ValueError(f"Estado '{estado}' inválido para '{var}'. Permitidos: {VALID_STATES[var]}")
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

    def __post_init__(self):
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
