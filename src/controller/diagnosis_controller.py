# src/controller/diagnosis_controller.py
import json
from typing import Dict, Any
from src.model.dtos import AstronomicalAlert
from src.model.transient_model import TransientModel
from src.view.console_view import ConsoleView


class DiagnosisController:
    def __init__(self, modelo: TransientModel, vista: ConsoleView):
        self.modelo = modelo
        self.vista = vista

    def procesar_alerta(self, datos_discretos: Dict[str, str | None], titulo: str = "") -> None:
        try:
            alerta = AstronomicalAlert(**datos_discretos)
            alerta.validar_estados()
            resultado = self.modelo.inferir(alerta)
            self.vista.mostrar_diagnostico(resultado, alerta.to_evidence_dict(), titulo=titulo)
        except Exception as e:
            self.vista.mostrar_error(str(e))

    def procesar_alerta_continua(self, datos_continuos: Dict[str, Any]) -> None:
        try:
            alerta = AstronomicalAlert.from_continuous_data(datos_continuos)
            resultado = self.modelo.inferir(alerta)
            self.vista.mostrar_diagnostico(
                resultado, alerta.to_evidence_dict(), titulo="Alerta desde mediciones físicas continuas"
            )
        except Exception as e:
            self.vista.mostrar_error(str(e))

    def cargar_lote_json(self, ruta_archivo: str = "data/casos_prueba.json") -> None:
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                lote = json.load(f)
            for item in lote:
                titulo = f"{item.get('id', 'CASO')}: {item.get('descripcion', '')}"
                self.procesar_alerta(item.get("evidencias", {}), titulo=titulo)
        except Exception as e:
            self.vista.mostrar_error(f"No se pudo procesar el lote JSON '{ruta_archivo}': {e}")

    def iniciar(self) -> None:
        while True:
            opcion = self.vista.mostrar_menu()
            if opcion == "1":
                datos = self.vista.solicitar_discretas()
                self.procesar_alerta(datos, titulo="Consulta interactiva (Estados discretos)")
            elif opcion == "2":
                try:
                    datos_cont = self.vista.solicitar_continuas()
                    self.procesar_alerta_continua(datos_cont)
                except ValueError:
                    self.vista.mostrar_error("Formato numérico inválido en las mediciones continuas.")
            elif opcion == "3":
                self.cargar_lote_json()
            elif opcion == "0":
                print("\nSaliendo del sistema de diagnóstico.")
                break
            else:
                self.vista.mostrar_error("Seleccione una opción válida entre 0 y 3.")