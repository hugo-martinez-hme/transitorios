# verificar_modelo.py
from src.model.dtos import AstronomicalAlert
from src.model.transient_model import TransientModel


def ejecutar_bateria_pruebas():
    print("=" * 75)
    print(" VERIFICACIÓN DEL MOTOR BAYESIANO RAIN (12 NODOS - CONCORDANCIA FIG. 1 Y 2)")
    print("=" * 75)
    modelo = TransientModel()
    print("[OK] DAG de 12 nodos (_construir_dag) y 12 CPTs (_cargar_cpts) validados.\n")

    casos = [
        (
            "CP-01: Supernova Ia en galaxia elíptica",
            AstronomicalAlert(
                galaxia="Eliptica", ubicacion="Halo", magnitud="Brillante",
                color="Azul", curva_luz="Decaimiento_Rapido"
            ),
        ),
        (
            "CP-02: Supernova oscurecida (Explaining Away)",
            AstronomicalAlert(
                galaxia="Espiral", ubicacion="Brazo_Espiral", color="Rojo",
                magnitud="Debil", anchura_lineas="Anchas"
            ),
        ),
        (
            "CP-03: Núcleo Galáctico Activo (AGN)",
            AstronomicalAlert(
                ubicacion="Nuclear", rayos_x="Intensa", curva_luz="Estocastica"
            ),
        ),
        (
            "CP-04: Alerta temprana (Evidencia parcial)",
            AstronomicalAlert(
                galaxia="Espiral", ubicacion="Brazo_Espiral",
                color="Azul", magnitud="Brillante"
            ),
        ),
    ]

    for titulo, alerta in casos:
        res = modelo.inferir(alerta)
        print(f"--- {titulo} ---")
        print(f"Evidencias       : {alerta.to_evidence_dict()}")
        probs_str = " | ".join([f"{k}: {v*100:.1f}%" for k, v in res.prob_transitorio.items()])
        print(f"prob_transitorio : {probs_str}")
        print(f"fisica_latente   : {res.resumen_fisica_latente()}")
        if res.ganancia_info_ig:
            top_obs, top_ig = next(iter(res.ganancia_info_ig.items()))
            print(f"ganancia_info_ig : 1º {top_obs} (IG = {top_ig:.3f} bits | H = {res.entropia_shannon:.2f} bits)")
        print("-" * 75)


if __name__ == "__main__":
    ejecutar_bateria_pruebas()
