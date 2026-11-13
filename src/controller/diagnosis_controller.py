# src/controller/diagnosis_controller.py
import json
from typing import Dict, Any
from src.model.dtos import AstronomicalAlert
from src.model.transient_model import TransientModel
from src.view.console_view import ConsoleView


class DiagnosisController:
    """Controlador MVC concordante con los atributos y métodos de la Figura 1."""

    def __init__(self, modelo: TransientModel, vista: ConsoleView):
        self.modelo = modelo
        self.vista = vista

    def procesar_alerta(
        self, datos: Dict[str, Any], continuo: bool = False, titulo: str = ""
    ) -> None:
        """Valida/discretiza la entrada en AstronomicalAlert, invoca al modelo y actualiza la vista."""
        try:
            if continuo:
                alerta = AstronomicalAlert.from_continuous(datos)
            else:
                alerta = AstronomicalAlert(**datos)
                alerta.validar_estados()

            resultado = self.modelo.inferir(alerta)
            self.vista.mostrar_diagnostico(resultado, alerta.to_evidence_dict(), titulo=titulo)
        except Exception as e:
            print(f"\n[ERROR]: {e}\n")

    def cargar_lote_json(self, ruta_archivo: str = "data/casos_prueba.json") -> None:
        """Carga y procesa una batería de alertas desde un archivo JSON (Figura 1)."""
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                lote = json.load(f)
            for item in lote:
                titulo = f"{item.get('id', 'CASO')}: {item.get('descripcion', '')}"
                self.procesar_alerta(item.get("evidencias", {}), continuo=False, titulo=titulo)
        except Exception as e:
            print(f"\n[ERROR al cargar JSON '{ruta_archivo}']: {e}\n")

    def iniciar(self) -> None:
        while True:
            opcion = self.vista.mostrar_menu()
            if opcion == "1":
                datos = self.vista.solicitar_discretas()
                self.procesar_alerta(datos, continuo=False, titulo="Diagnóstico desde estados discretos")
            elif opcion == "2":
                try:
                    datos_cont = self.vista.solicitar_continuas()
                    self.procesar_alerta(datos_cont, continuo=True, titulo="Diagnóstico desde mediciones continuas")
                except ValueError:
                    print("\n[ERROR]: Introduzca un valor numérico válido.\n")
            elif opcion == "3":
                self.cargar_lote_json()
            elif opcion == "0":
                print("\nCerrando el sistema RAIN.")
                break
            else:
                print("\n[!] Seleccione una opción válida (0-3).")
