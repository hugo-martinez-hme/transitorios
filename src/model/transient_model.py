# src/model/transient_model.py
import math
import warnings
from typing import Dict

warnings.filterwarnings("ignore", category=FutureWarning)

from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

from src.model.dtos import AstronomicalAlert, DiagnosisResult, VALID_STATES

LATENT_NODES = [
    "Extincion_Polvo",
    "Temperatura_Intrinseca",
    "Luminosidad_Pico",
    "Velocidad_Expansion",
]


class TransientModel:
    def __init__(self):
        self.red = self._construir_topologia()
        self._cargar_cpts()
        self.red.check_model()
        self.motor_inferencia = VariableElimination(self.red)

    def _construir_topologia(self) -> DiscreteBayesianNetwork:
        """Define la estructura del DAG de 12 nodos en 4 estratos (Sección 3 del PDF)."""
        aristas = [
            # Nivel 1 -> Nivel 2 y 3
            ("Galaxia_Anfitriona", "Tipo_Transitorio"),
            ("Galaxia_Anfitriona", "Ubicacion_Galactica"),
            # Nivel 2 -> Nivel 3
            ("Tipo_Transitorio", "Ubicacion_Galactica"),
            ("Tipo_Transitorio", "Temperatura_Intrinseca"),
            ("Tipo_Transitorio", "Luminosidad_Pico"),
            ("Tipo_Transitorio", "Velocidad_Expansion"),
            # Enlaces internos Nivel 3
            ("Ubicacion_Galactica", "Extincion_Polvo"),
            ("Temperatura_Intrinseca", "Luminosidad_Pico"),
            # Nivel 3 -> Nivel 4 (Observables e interacciones en V)
            ("Luminosidad_Pico", "Magnitud_Aparente"),
            ("Extincion_Polvo", "Magnitud_Aparente"),
            ("Temperatura_Intrinseca", "Color_Observado"),
            ("Extincion_Polvo", "Color_Observado"),
            ("Tipo_Transitorio", "Emision_RayosX"),
            ("Temperatura_Intrinseca", "Emision_RayosX"),
            ("Velocidad_Expansion", "Anchura_Lineas_Espect"),
            ("Temperatura_Intrinseca", "Anchura_Lineas_Espect"),
            ("Tipo_Transitorio", "Forma_Curva_Luz"),
            ("Velocidad_Expansion", "Forma_Curva_Luz"),
        ]
        return DiscreteBayesianNetwork(aristas)

    def _cargar_cpts(self) -> None:
        """Carga las 12 Tablas de Probabilidad Condicional exactas del Anexo A."""
        # A.1. Galaxia_Anfitriona
        cpd_galaxia = TabularCPD(
            variable="Galaxia_Anfitriona",
            variable_card=3,
            values=[[0.60], [0.25], [0.15]],
            state_names={"Galaxia_Anfitriona": VALID_STATES["Galaxia_Anfitriona"]},
        )

        # A.2. Tipo_Transitorio | Galaxia_Anfitriona
        cpd_tipo = TabularCPD(
            variable="Tipo_Transitorio",
            variable_card=4,
            values=[
                [0.30, 0.55, 0.20],  # SN_Ia
                [0.40, 0.01, 0.55],  # SN_II
                [0.15, 0.34, 0.05],  # AGN
                [0.15, 0.10, 0.20],  # Variable_Estelar
            ],
            evidence=["Galaxia_Anfitriona"],
            evidence_card=[3],
            state_names={
                "Tipo_Transitorio": VALID_STATES["Tipo_Transitorio"],
                "Galaxia_Anfitriona": VALID_STATES["Galaxia_Anfitriona"],
            },
        )

        # A.3. Ubicacion_Galactica | Galaxia_Anfitriona, Tipo_Transitorio
        cpd_ubicacion = TabularCPD(
            variable="Ubicacion_Galactica",
            variable_card=3,
            values=[
                # Espiral (Ia, II, AGN, Var) | Eliptica (Ia, II, AGN, Var) | Irregular (Ia, II, AGN, Var)
                [0.10, 0.05, 0.98, 0.20, 0.15, 0.10, 0.98, 0.25, 0.10, 0.05, 0.98, 0.15],  # Nuclear
                [0.65, 0.90, 0.01, 0.60, 0.05, 0.10, 0.01, 0.05, 0.70, 0.90, 0.01, 0.70],  # Brazo_Espiral
                [0.25, 0.05, 0.01, 0.20, 0.80, 0.80, 0.01, 0.70, 0.20, 0.05, 0.01, 0.15],  # Halo
            ],
            evidence=["Galaxia_Anfitriona", "Tipo_Transitorio"],
            evidence_card=[3, 4],
            state_names={
                "Ubicacion_Galactica": VALID_STATES["Ubicacion_Galactica"],
                "Galaxia_Anfitriona": VALID_STATES["Galaxia_Anfitriona"],
                "Tipo_Transitorio": VALID_STATES["Tipo_Transitorio"],
            },
        )

        # A.4. Extincion_Polvo | Ubicacion_Galactica
        cpd_polvo = TabularCPD(
            variable="Extincion_Polvo",
            variable_card=3,
            values=[
                [0.15, 0.20, 0.90],  # Baja
                [0.40, 0.50, 0.09],  # Moderada
                [0.45, 0.30, 0.01],  # Severa
            ],
            evidence=["Ubicacion_Galactica"],
            evidence_card=[3],
            state_names={
                "Extincion_Polvo": VALID_STATES["Extincion_Polvo"],
                "Ubicacion_Galactica": VALID_STATES["Ubicacion_Galactica"],
            },
        )

        # A.5. Temperatura_Intrinseca | Tipo_Transitorio
        cpd_temp = TabularCPD(
            variable="Temperatura_Intrinseca",
            variable_card=3,
            values=[
                [0.55, 0.70, 0.75, 0.10],  # Alta
                [0.40, 0.25, 0.20, 0.25],  # Media
                [0.05, 0.05, 0.05, 0.65],  # Baja
            ],
            evidence=["Tipo_Transitorio"],
            evidence_card=[4],
            state_names={
                "Temperatura_Intrinseca": VALID_STATES["Temperatura_Intrinseca"],
                "Tipo_Transitorio": VALID_STATES["Tipo_Transitorio"],
            },
        )

        # A.6. Luminosidad_Pico | Tipo_Transitorio, Temperatura_Intrinseca
        cpd_lum = TabularCPD(
            variable="Luminosidad_Pico",
            variable_card=3,
            values=[
                # SN_Ia (A,M,B) | SN_II (A,M,B) | AGN (A,M,B) | Var (A,M,B)
                [0.90, 0.80, 0.55, 0.55, 0.30, 0.10, 0.85, 0.65, 0.35, 0.05, 0.02, 0.01],  # Muy_Alta
                [0.09, 0.18, 0.40, 0.40, 0.60, 0.65, 0.14, 0.30, 0.45, 0.35, 0.23, 0.09],  # Moderada
                [0.01, 0.02, 0.05, 0.05, 0.10, 0.25, 0.01, 0.05, 0.20, 0.60, 0.75, 0.90],  # Baja
            ],
            evidence=["Tipo_Transitorio", "Temperatura_Intrinseca"],
            evidence_card=[4, 3],
            state_names={
                "Luminosidad_Pico": VALID_STATES["Luminosidad_Pico"],
                "Tipo_Transitorio": VALID_STATES["Tipo_Transitorio"],
                "Temperatura_Intrinseca": VALID_STATES["Temperatura_Intrinseca"],
            },
        )

        # A.7. Velocidad_Expansion | Tipo_Transitorio
        cpd_vel = TabularCPD(
            variable="Velocidad_Expansion",
            variable_card=3,
            values=[
                [0.85, 0.40, 0.02, 0.01],  # Muy_Alta
                [0.14, 0.58, 0.08, 0.04],  # Moderada
                [0.01, 0.02, 0.90, 0.95],  # Baja_Nula
            ],
            evidence=["Tipo_Transitorio"],
            evidence_card=[4],
            state_names={
                "Velocidad_Expansion": VALID_STATES["Velocidad_Expansion"],
                "Tipo_Transitorio": VALID_STATES["Tipo_Transitorio"],
            },
        )

        # A.8. Magnitud_Aparente | Luminosidad_Pico, Extincion_Polvo
        cpd_mag = TabularCPD(
            variable="Magnitud_Aparente",
            variable_card=3,
            values=[
                # Muy_Alta (B,M,S) | Moderada (B,M,S) | Baja (B,M,S)
                [0.90, 0.55, 0.10, 0.35, 0.10, 0.02, 0.05, 0.02, 0.01],  # Brillante
                [0.09, 0.40, 0.35, 0.55, 0.60, 0.23, 0.25, 0.13, 0.04],  # Intermedia
                [0.01, 0.05, 0.55, 0.10, 0.30, 0.75, 0.70, 0.85, 0.95],  # Debil
            ],
            evidence=["Luminosidad_Pico", "Extincion_Polvo"],
            evidence_card=[3, 3],
            state_names={
                "Magnitud_Aparente": VALID_STATES["Magnitud_Aparente"],
                "Luminosidad_Pico": VALID_STATES["Luminosidad_Pico"],
                "Extincion_Polvo": VALID_STATES["Extincion_Polvo"],
            },
        )

        # A.9. Color_Observado | Temperatura_Intrinseca, Extincion_Polvo
        cpd_color = TabularCPD(
            variable="Color_Observado",
            variable_card=3,
            values=[
                # Alta (B,M,S) | Media (B,M,S) | Baja (B,M,S)
                [0.90, 0.45, 0.05, 0.20, 0.08, 0.01, 0.03, 0.01, 0.01],  # Azul
                [0.09, 0.45, 0.25, 0.70, 0.52, 0.14, 0.17, 0.09, 0.02],  # Neutro
                [0.01, 0.10, 0.70, 0.10, 0.40, 0.85, 0.80, 0.90, 0.97],  # Rojo
            ],
            evidence=["Temperatura_Intrinseca", "Extincion_Polvo"],
            evidence_card=[3, 3],
            state_names={
                "Color_Observado": VALID_STATES["Color_Observado"],
                "Temperatura_Intrinseca": VALID_STATES["Temperatura_Intrinseca"],
                "Extincion_Polvo": VALID_STATES["Extincion_Polvo"],
            },
        )

        # A.10. Emision_RayosX | Tipo_Transitorio, Temperatura_Intrinseca
        cpd_rayosx = TabularCPD(
            variable="Emision_RayosX",
            variable_card=3,
            values=[
                # SN_Ia (A,M,B) | SN_II (A,M,B) | AGN (A,M,B) | Var (A,M,B)
                [0.03, 0.01, 0.01, 0.10, 0.03, 0.01, 0.90, 0.75, 0.45, 0.03, 0.01, 0.01],  # Intensa
                [0.27, 0.14, 0.04, 0.55, 0.37, 0.14, 0.09, 0.23, 0.45, 0.27, 0.14, 0.04],  # Debil
                [0.70, 0.85, 0.95, 0.35, 0.60, 0.85, 0.01, 0.02, 0.10, 0.70, 0.85, 0.95],  # Nula
            ],
            evidence=["Tipo_Transitorio", "Temperatura_Intrinseca"],
            evidence_card=[4, 3],
            state_names={
                "Emision_RayosX": VALID_STATES["Emision_RayosX"],
                "Tipo_Transitorio": VALID_STATES["Tipo_Transitorio"],
                "Temperatura_Intrinseca": VALID_STATES["Temperatura_Intrinseca"],
            },
        )

        # A.11. Anchura_Lineas_Espect | Velocidad_Expansion, Temperatura_Intrinseca
        cpd_lineas = TabularCPD(
            variable="Anchura_Lineas_Espect",
            variable_card=3,
            values=[
                # Muy_Alta (A,M,B) | Moderada (A,M,B) | Baja_Nula (A,M,B)
                [0.95, 0.90, 0.85, 0.45, 0.30, 0.20, 0.10, 0.05, 0.02],  # Anchas
                [0.03, 0.08, 0.12, 0.50, 0.65, 0.75, 0.65, 0.70, 0.68],  # Estrechas
                [0.02, 0.02, 0.03, 0.05, 0.05, 0.05, 0.25, 0.25, 0.30],  # Ausentes
            ],
            evidence=["Velocidad_Expansion", "Temperatura_Intrinseca"],
            evidence_card=[3, 3],
            state_names={
                "Anchura_Lineas_Espect": VALID_STATES["Anchura_Lineas_Espect"],
                "Velocidad_Expansion": VALID_STATES["Velocidad_Expansion"],
                "Temperatura_Intrinseca": VALID_STATES["Temperatura_Intrinseca"],
            },
        )

        # A.12. Forma_Curva_Luz | Tipo_Transitorio, Velocidad_Expansion
        cpd_curva = TabularCPD(
            variable="Forma_Curva_Luz",
            variable_card=3,
            values=[
                # SN_Ia (MA,M,BN) | SN_II (MA,M,BN) | AGN (MA,M,BN) | Var (MA,M,BN)
                [0.95, 0.85, 0.60, 0.25, 0.10, 0.15, 0.15, 0.10, 0.03, 0.25, 0.15, 0.08],  # Decaimiento_Rapido
                [0.03, 0.10, 0.15, 0.70, 0.85, 0.55, 0.05, 0.05, 0.02, 0.05, 0.05, 0.02],  # Meseta
                [0.02, 0.05, 0.25, 0.05, 0.05, 0.30, 0.80, 0.85, 0.95, 0.70, 0.80, 0.90],  # Estocastica
            ],
            evidence=["Tipo_Transitorio", "Velocidad_Expansion"],
            evidence_card=[4, 3],
            state_names={
                "Forma_Curva_Luz": VALID_STATES["Forma_Curva_Luz"],
                "Tipo_Transitorio": VALID_STATES["Tipo_Transitorio"],
                "Velocidad_Expansion": VALID_STATES["Velocidad_Expansion"],
            },
        )

        self.red.add_cpds(
            cpd_galaxia, cpd_tipo, cpd_ubicacion, cpd_polvo, cpd_temp,
            cpd_lum, cpd_vel, cpd_mag, cpd_color, cpd_rayosx, cpd_lineas, cpd_curva
        )

    @staticmethod
    def _calcular_entropia(distribucion: Dict[str, float]) -> float:
        """Calcula la Entropía de Shannon H(T|e) en bits."""
        entropia = 0.0
        for p in distribucion.values():
            if p > 1e-12:
                entropia -= p * math.log2(p)
        return entropia

    def _consultar_nodo(self, variable: str, evidencias: Dict[str, str]) -> Dict[str, float]:
        """Ejecuta VariableElimination para una variable y devuelve un diccionario limpio."""
        factor = self.motor_inferencia.query(variables=[variable], evidence=evidencias, show_progress=False)
        estados = VALID_STATES[variable]
        return {estado: float(factor.values[i]) for i, estado in enumerate(estados)}

    def inferir_fisica_latente(self, evidencias: Dict[str, str]) -> Dict[str, Dict[str, float]]:
        """Infiere la distribución posterior de los 4 nodos físicos latentes del Nivel 3."""
        return {nodo: self._consultar_nodo(nodo, evidencias) for nodo in LATENT_NODES}

    def calcular_ganancia_informacion(self, alerta: AstronomicalAlert, entropia_actual: float) -> Dict[str, float]:
        """Calcula IG(T; O_i | e) para cada observable aún no medido."""
        evidencias_base = alerta.to_evidence_dict()
        faltantes = alerta.obtener_observables_faltantes()
        ganancias = {}

        for obs in faltantes:
            dist_obs = self._consultar_nodo(obs, evidencias_base)
            entropia_esperada = 0.0
            for estado_obs, prob_obs in dist_obs.items():
                if prob_obs > 1e-6:
                    ev_hipotetica = dict(evidencias_base)
                    ev_hipotetica[obs] = estado_obs
                    dist_t_cond = self._consultar_nodo("Tipo_Transitorio", ev_hipotetica)
                    entropia_esperada += prob_obs * self._calcular_entropia(dist_t_cond)

            ig = max(0.0, entropia_actual - entropia_esperada)
            ganancias[obs] = round(ig, 4)

        return dict(sorted(ganancias.items(), key=lambda item: item[1], reverse=True))

    def inferir(self, alerta: AstronomicalAlert) -> DiagnosisResult:
        """Ejecuta el flujo completo: diagnóstico, física latente y ganancia de información."""
        alerta.validar_estados()
        evidencias = alerta.to_evidence_dict()

        dist_transitorio = self._consultar_nodo("Tipo_Transitorio", evidencias)
        clase_top, confianza_top = max(dist_transitorio.items(), key=lambda x: x[1])
        entropia = self._calcular_entropia(dist_transitorio)

        latentes = self.inferir_fisica_latente(evidencias)
        recomendaciones = self.calcular_ganancia_informacion(alerta, entropia)

        return DiagnosisResult(
            probabilidades_transitorio=dist_transitorio,
            estados_fisicos_latentes=latentes,
            clase_predicha=clase_top,
            confianza=confianza_top,
            entropia_shannon=round(entropia, 4),
            recomendacion_seguimiento=recomendaciones,
        )