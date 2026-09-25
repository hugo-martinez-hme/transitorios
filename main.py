from pgmpy.inference import VariableElimination
from src.model import construir_red_transitorios

def main():
    print("=" * 60)
    print("PROTOTIPO: RED BAYESIANA DE EVENTOS TRANSITORIOS ASTROFÍSICOS")
    print("=" * 60)
    
    modelo = construir_red_transitorios()
    inferencia = VariableElimination(modelo)

    print(f"Modelo compilado correctamente.")
    print(f"Nodos registrados: {len(modelo.nodes())}")
    print(f"Arcos causales:    {len(modelo.edges())}")

    print("\n[Prueba Diagnóstica Preliminar]")
    print("Evidencias: OffsetGalactico = Nuclear, EmisionRayosX = Detectada")
    
    resultado = inferencia.query(
        variables=['TipoTransitorio'],
        evidence={'OffsetGalactico': 'Nuclear', 'EmisionRayosX': 'Detectada'}
    )
    print("\nDistribución a posteriori inferida:")
    print(resultado)
    print("=" * 60)

if __name__ == '__main__':
    main()
