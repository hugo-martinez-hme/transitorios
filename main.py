from pgmpy.inference import VariableElimination
from src.model import construir_red_transitorios

def formatear_distribucion(phi) -> str:
    lineas = []
    estados = phi.state_names[phi.variables[0]]
    for estado, prob in zip(estados, phi.values):
        lineas.append(f"  {estado:12s}: {prob * 100:6.2f}%")
    return "\n".join(lineas)

def main():
    modelo = construir_red_transitorios()
    infer = VariableElimination(modelo)

    print("=" * 65)
    print("SISTEMA BAYESIANO DE DIAGNÓSTICO DE TRANSITORIOS ASTROFÍSICOS")
    print("=" * 65)

    # Escenario 1: Alerta temprana en periferia de galaxia espiral
    print("\n[ESCENARIO 1: Alerta temprana periférica]")
    evidencia_1 = {
        'TipoGalaxia': 'Espiral_StarForming',
        'OffsetGalactico': 'Periferico',
        'ColorObservado': 'Azul_Aparente'
    }
    print(f"Evidencias: {evidencia_1}")
    res_1 = infer.query(['TipoTransitorio'], evidence=evidencia_1)
    print(formatear_distribucion(res_1))

    # Escenario 2: Restricción astrofísica fuerte (Galaxia elíptica)
    print("\n[ESCENARIO 2: Mismas observaciones en galaxia elíptica pasiva]")
    evidencia_2 = {
        'TipoGalaxia': 'Eliptica_Pasiva',
        'OffsetGalactico': 'Periferico',
        'ColorObservado': 'Azul_Aparente'
    }
    print(f"Evidencias: {evidencia_2}")
    res_2 = infer.query(['TipoTransitorio'], evidence=evidencia_2)
    print(formatear_distribucion(res_2))

    # Escenario 3: Inter-causalidad (Explaining Away mediante extinción por polvo)
    print("\n[ESCENARIO 3: Objeto observado en ROJO. ¿Es frío o hay polvo?]")
    res_3a = infer.query(['ColorIntrinseco'], evidence={'ColorObservado': 'Rojo_Aparente'})
    print("Probabilidad de color intrínseco sin conocer el polvo:")
    print(formatear_distribucion(res_3a))

    print("\nSe detecta alta columna de polvo interestelar (ExtincionPolvo = Alta):")
    res_3b = infer.query(
        ['ColorIntrinseco'],
        evidence={'ColorObservado': 'Rojo_Aparente', 'ExtincionPolvo': 'Alta'}
    )
    print(formatear_distribucion(res_3b))
    print("=" * 65)

if __name__ == '__main__':
    main()
