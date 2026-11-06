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
    "Anchura_Lineas_Espect": ["Anchas", "Estrechas", "Ausentes"],
    "Forma_Curva_Luz": ["Decaimiento_Rapido", "Meseta", "Estocastica"],
}

OBSERVABLE_NODES = [
    "Galaxia_Anfitriona",
    "Ubicacion_Galactica",
    "Color_Observado",
    "Magnitud_Aparente",
    "Emision_RayosX",
    "Anchura_Lineas_Espect",
    "Forma_Curva_Luz",
]


@dataclass
class AstronomicalAlert:
    galaxia: Optional[str] = None
    ubicacion: Optional[str] = None
    color: Optional[str] = None
    magnitud: Optional[str] = None
    rayos_x: Optional[str] = None
    anchura_lineas: Optional[str] = None
    curva_luz: Optional[str] = None

    @classmethod
    def from_continuous_data(cls, raw: Dict[str, float | str]) -> "AstronomicalAlert":
        """Discretiza mediciones físicas continuas según la Tabla 2 del diseño."""
        galaxia = raw.get("galaxia")

        # Distancia galactocéntrica r (kpc)
        ubicacion = raw.get("ubicacion")
        if "r_kpc" in raw and raw["r_kpc"] is not None:
            r = float(raw["r_kpc"])
            ubicacion = "Nuclear" if r < 1.0 else ("Halo" if r > 15.0 else "Brazo_Espiral")

        # Índice de color (g - r) en mag
        color = raw.get("color")
        if "g_minus_r" in raw and raw["g_minus_r"] is not None:
            gr = float(raw["g_minus_r"])
            color = "Azul" if gr < 0.0 else ("Rojo" if gr > 0.5 else "Neutro")

        # Magnitud aparente banda óptica m_V
        magnitud = raw.get("magnitud")
        if "m_v" in raw and raw["m_v"] is not None:
            mv = float(raw["m_v"])
            magnitud = "Brillante" if mv < 17.0 else ("Debil" if mv > 19.5 else "Intermedia")

        # Luminosidad en rayos X L_X (erg/s)
        rayos_x = raw.get("rayos_x")
        if "l_x" in raw and raw["l_x"] is not None:
            lx = float(raw["l_x"])
            rayos_x = "Intensa" if lx > 1e42 else ("Debil" if lx >= 1e39 else "Nula")

        # Ensanchamiento Doppler FWHM (km/s)
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

    def to_evidence_dict(self) -> Dict[str, str]:
        """Devuelve el diccionario de evidencias observadas (no nulas) para pgmpy."""
        mapping = {
            "Galaxia_Anfitriona": self.galaxia,
            "Ubicacion_Galactica": self.ubicacion,
            "Color_Observado": self.color,
            "Magnitud_Aparente": self.magnitud,
            "Emision_RayosX": self.rayos_x,
            "Anchura_Lineas_Espect": self.anchura_lineas,
            "Forma_Curva_Luz": self.curva_luz,
        }
        return {k: v for k, v in mapping.items() if v is not None}

    def obtener_observables_faltantes(self) -> List[str]:
        """Identifica qué nodos observables aún no han sido medidos."""
        evidencias = self.to_evidence_dict()
        return [nodo for nodo in OBSERVABLE_NODES if nodo not in evidencias]

    def validar_estados(self) -> bool:
        """Verifica que todos los estados activos pertenezcan al dominio."""
        for var, estado in self.to_evidence_dict().items():
            if estado not in VALID_STATES[var]:
                raise ValueError(f"Estado '{estado}' inválido para '{var}'. Permitidos: {VALID_STATES[var]}")
        return True


@dataclass
class DiagnosisResult:
    probabilidades_transitorio: Dict[str, float]
    estados_fisicos_latentes: Dict[str, Dict[str, float]]
    clase_predicha: str
    confianza: float
    entropia_shannon: float
    recomendacion_seguimiento: Dict[str, float] = field(default_factory=dict)

    def generar_explicacion_causal(self) -> str:
        """Genera una síntesis de los estados latentes dominantes del Nivel 3."""
        partes = []
        for var, dist in self.estados_fisicos_latentes.items():
            estado_top = max(dist.items(), key=lambda x: x[1])
            partes.append(f"{var}: {estado_top[0]} ({estado_top[1]*100:.1f}%)")
        return " | ".join(partes)