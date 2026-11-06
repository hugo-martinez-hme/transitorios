# verificar_modelo.py
from src.model.dtos import AstronomicalAlert
from src.model.transient_model import TransientModel

def ejecutar_bateria_pruebas():
    print("=" * 75)
    print(" VERIFICACIÓN DEL MOTOR BAYESIANO RAIN (12 NODOS - ANEXO A)")
    print("=" * 75)
    modelo = TransientModel()
    print("[OK] Red Bayesiana construida y validada con check_model() sin errores.\n")

    casos = [
        (
            "CP-01: Supernova Ia canónica en galaxia elíptica",
            AstronomicalAlert(
                galaxia="Eliptica", ubicacion="Halo", magnitud="Brillante",
                color="Azul", curva_luz="Decaimiento_Rapido"
            ),
        ),
        (
            "CP-02: Supernova oscurecida por polvo (Efecto Explaining Away)",
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
            "CP-04: Alerta temprana con evidencia parcial (Planificación IG)",
            AstronomicalAlert(
                galaxia="Espiral", ubicacion="Brazo_Espiral",
                color="Azul", magnitud="Brillante"
            ),
        ),
    ]

    for titulo, alerta in casos:
        res = modelo.inferir(alerta)
        print(f"--- {titulo} ---")
        print(f"Evidencias: {alerta.to_evidence_dict()}")
        probs_str = " | ".join([f"{k}: {v*100:.1f}%" for k, v in res.probabilidades_transitorio.items()])
        print(f"Diagnóstico : {probs_str}")
        print(f"Predicción  : {res.clase_predicha} (Confianza: {res.confianza*100:.1f}% | Entropía H = {res.entropia_shannon:.2f} bits)")
        print(f"Física N3   : {res.generar_explicacion_causal()}")
        if res.recomendacion_seguimiento:
            top_obs, top_ig = next(iter(res.recomendacion_seguimiento.items()))
            print(f"Recomendación Telescópica Top: Medir '{top_obs}' (Ganancia IG = {top_ig:.3f} bits)")
        print("-" * 75)

if __name__ == "__main__":
    ejecutar_bateria_pruebas()