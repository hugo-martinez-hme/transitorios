import pgmpy
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

print(f"pgmpy versión: {pgmpy.__version__}")

modelo = DiscreteBayesianNetwork([('A', 'B')])
cpd_a = TabularCPD('A', 2, [[0.7], [0.3]])
cpd_b = TabularCPD('B', 2, [[0.9, 0.2], [0.1, 0.8]], evidence=['A'], evidence_card=[2])
modelo.add_cpds(cpd_a, cpd_b)
assert modelo.check_model()

infer = VariableElimination(modelo)
print("\nInferencia funcional:")
print(infer.query(['B'], evidence={'A': 0}))
