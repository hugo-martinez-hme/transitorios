from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

# 1. Definición del grafo: TipoTransitorio influye en la Posición y en el Color
modelo = DiscreteBayesianNetwork([
    ('TipoTransitorio', 'OffsetGalactico'),
    ('TipoTransitorio', 'Color_gr')
])

# 2. CPT del nodo raíz (Probabilidades a priori de la población)
# Estados: [SN_Ia, SN_II, AGN, Variable]
cpd_tipo = TabularCPD(
    variable='TipoTransitorio',
    variable_card=4,
    values=[[0.30], [0.25], [0.15], [0.30]],
    state_names={'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']}
)

# 3. CPT de OffsetGalactico condicionado por TipoTransitorio
# Filas: [Nuclear, Periferico] | Columnas: [SN_Ia, SN_II, AGN, Variable]
cpd_offset = TabularCPD(
    variable='OffsetGalactico',
    variable_card=2,
    values=[
        [0.10, 0.05, 0.98, 0.20],  # Nuclear (el AGN está siempre en el centro)
        [0.90, 0.95, 0.02, 0.80]   # Periferico
    ],
    evidence=['TipoTransitorio'],
    evidence_card=[4],
    state_names={
        'OffsetGalactico': ['Nuclear', 'Periferico'],
        'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']
    }
)

# 4. CPT de Color_gr condicionado por TipoTransitorio
# Filas: [Azul_Caliente, Rojo_Frio] | Columnas: [SN_Ia, SN_II, AGN, Variable]
cpd_color = TabularCPD(
    variable='Color_gr',
    variable_card=2,
    values=[
        [0.60, 0.85, 0.80, 0.20],  # Azul_Caliente (SN II y AGN jóvenes son muy calientes)
        [0.40, 0.15, 0.20, 0.80]   # Rojo_Frio
    ],
    evidence=['TipoTransitorio'],
    evidence_card=[4],
    state_names={
        'Color_gr': ['Azul_Caliente', 'Rojo_Frio'],
        'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']
    }
)

modelo.add_cpds(cpd_tipo, cpd_offset, cpd_color)
assert modelo.check_model(), "Inconsistencia matemática en las probabilidades"

# 5. Inferencia diagnóstica (razonamiento hacia atrás: de síntomas a causa)
inferencia = VariableElimination(modelo)

print("--- CASO 1: Telescopio detecta transitorio AZUL en el NÚCLEO galáctico ---")
res1 = inferencia.query(
    variables=['TipoTransitorio'],
    evidence={'OffsetGalactico': 'Nuclear', 'Color_gr': 'Azul_Caliente'}
)
print(res1)

print("\n--- CASO 2: Telescopio detecta transitorio AZUL en la PERIFERIA galáctica ---")
res2 = inferencia.query(
    variables=['TipoTransitorio'],
    evidence={'OffsetGalactico': 'Periferico', 'Color_gr': 'Azul_Caliente'}
)
print(res2)
