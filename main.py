# main.py
from src.model.transient_model import TransientModel
from src.view.console_view import ConsoleView
from src.controller.diagnosis_controller import DiagnosisController


def main():
    modelo = TransientModel()
    vista = ConsoleView()
    controlador = DiagnosisController(modelo=modelo, vista=vista)
    controlador.iniciar()


if __name__ == "__main__":
    main()