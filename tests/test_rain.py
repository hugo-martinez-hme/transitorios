import unittest
from src.model.dtos import AstronomicalAlert, DiagnosisResult
from src.model.transient_model import TransientModel
from src.view.console_view import ConsoleView
from src.controller.diagnosis_controller import DiagnosisController


class TestConcordanciaArquitectura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modelo = TransientModel()

    def test_metodos_y_atributos_figura_1(self):
        """Comprueba que todas las clases poseen exactamente los miembros de la Figura 1."""
        # ConsoleView
        vista = ConsoleView()
        for metodo in ("mostrar_menu", "solicitar_discretas", "solicitar_continuas", "mostrar_diagnostico"):
            self.assertTrue(hasattr(vista, metodo), f"Falta {metodo} en ConsoleView")

        # DiagnosisController
        ctrl = DiagnosisController(modelo=self.modelo, vista=vista)
        self.assertIs(ctrl.modelo, self.modelo)
        self.assertIs(ctrl.vista, vista)
        for metodo in ("procesar_alerta", "cargar_lote_json"):
            self.assertTrue(hasattr(ctrl, metodo), f"Falta {metodo} en DiagnosisController")

        # AstronomicalAlert
        alerta = AstronomicalAlert.from_continuous({"galaxia": "Espiral", "r_kpc": 0.5})
        self.assertIn("Ubicacion_Galactica", alerta.to_evidence_dict())
        self.assertIn("Forma_Curva_Luz", alerta.obtener_faltantes())

        # TransientModel & DiagnosisResult
        res: DiagnosisResult = self.modelo.inferir(alerta)
        for attr in ("prob_transitorio", "fisica_latente", "ganancia_info_ig"):
            self.assertTrue(hasattr(res, attr), f"Falta {attr} en DiagnosisResult")

    def test_nodos_y_aristas_figura_2(self):
        """Comprueba que los 12 nodos coinciden con la Figura 2 del documento."""
        nodos_esperados = {
            "Galaxia_Anfitriona", "Tipo_Transitorio", "Ubicacion_Galactica",
            "Extincion_Polvo", "Luminosidad_Pico", "Temperatura_Intrinseca",
            "Velocidad_Expansion", "Color_Observado", "Magnitud_Aparente",
            "Emision_RayosX", "Anchura_Lineas", "Forma_Curva_Luz"
        }
        self.assertEqual(set(self.modelo.red.nodes()), nodos_esperados)
        self.assertEqual(len(self.modelo.red.edges()), 18)

    def test_casos_prueba_seccion_6(self):
        """Verifica CP-01, CP-02, CP-03 y CP-04."""
        # CP-01
        cp01 = self.modelo.inferir(AstronomicalAlert(
            galaxia="Eliptica", ubicacion="Halo", magnitud="Brillante",
            color="Azul", curva_luz="Decaimiento_Rapido"
        ))
        self.assertEqual(cp01.clase_predicha, "SN_Ia")
        self.assertGreater(cp01.confianza, 0.90)

        # CP-02
        cp02 = self.modelo.inferir(AstronomicalAlert(
            galaxia="Espiral", ubicacion="Brazo_Espiral", color="Rojo",
            magnitud="Debil", anchura_lineas="Anchas"
        ))
        self.assertGreater(cp02.fisica_latente["Extincion_Polvo"]["Severa"], 0.75)

        # CP-03
        cp03 = self.modelo.inferir(AstronomicalAlert(
            ubicacion="Nuclear", rayos_x="Intensa", curva_luz="Estocastica"
        ))
        self.assertEqual(cp03.clase_predicha, "AGN")
        self.assertGreater(cp03.confianza, 0.95)

        # CP-04
        cp04 = self.modelo.inferir(AstronomicalAlert(
            galaxia="Espiral", ubicacion="Brazo_Espiral", color="Azul", magnitud="Brillante"
        ))
        top_ig = next(iter(cp04.ganancia_info_ig.keys()))
        self.assertEqual(top_ig, "Forma_Curva_Luz")


if __name__ == "__main__":
    unittest.main(verbosity=2)
