# Arquitectura del Sistema: Diagnóstico de Transitorios Astrofísicos

## 1. Topología del Grafo Causal (DAG)
El sistema modela 9 variables aleatorias discretas para inferir la naturaleza física de fuentes transitorias bajo incertidumbre observacional.

```
       [TipoGalaxia]
             |
             v
     [TipoTransitorio]
     /   /    |    \    \
    /   /     |     \    \
   v   v      v      v    v
[Offset] [Decaimiento] [RayosX] [Periodico] [ColorIntrinseco]  [ExtincionPolvo]
                                                   \                 /
                                                    v               v
                                                    [ColorObservado]
```

## 2. Definición Formal de Variables y Estados

| Variable | Estados | Rol Causal |
| :--- | :--- | :--- |
| `TipoGalaxia` | `Espiral_StarForming`, `Eliptica_Pasiva` | Prior contextual (población estelar) |
| `TipoTransitorio` | `SN_Ia`, `SN_II`, `AGN`, `Variable` | Hipótesis diagnóstica (nodo central) |
| `OffsetGalactico` | `Nuclear`, `Periferico` | Manifestación geométrica |
| `TasaDecaimiento`| `Rapida`, `Lenta_Meseta` | Manifestación fotométrica temporal |
| `EmisionRayosX` | `Detectada`, `NoDetectada` | Manifestación de alta energía |
| `ComportamientoTemporal` | `Evento_Unico`, `Periodico` | Historial de recurrencia |
| `ColorIntrinseco` | `Azul_Caliente`, `Rojo_Frio` | Proceso térmico emisor |
| `ExtincionPolvo` | `Baja`, `Alta` | Interferencia del medio interestelar |
| `ColorObservado` | `Azul_Aparente`, `Rojo_Aparente` | Evidencia observacional directa |

## 3. Justificación Física y Causal
* **Incompatibilidad de colapso de núcleo en elípticas:** Las supernovas de colapso gravitatorio ($\text{SN\_II}$) proceden de estrellas masivas de vida corta ($<50 \times 10^6$ años). En galaxias elípticas pasivas no hay formación estelar reciente, por lo que $P(\text{SN\_II} \mid \text{Eliptica}) \approx 0$.
* **Localización nuclear estricta:** La actividad por acreción en un agujero negro supermasivo ($\text{AGN}$) solo ocurre en el pozo gravitatorio central de la galaxia ($P(\text{Nuclear} \mid \text{AGN}) \approx 1$).
* **Estructura en V (*Collider* / Inter-causalidad):** El nodo `ColorObservado` tiene dos causas independientes: la emisión térmica original (`ColorIntrinseco`) y la dispersión por polvo en la línea de visión (`ExtincionPolvo`). Al observar un transitorio rojo, conocer si la extinción por polvo es alta o baja modifica retrospectivamente la probabilidad sobre su temperatura intrínseca (*explaining away*).

## 4. Factorización de la Distribución Conjunta
$$P(V) = P(G) \cdot P(T \mid G) \cdot P(O \mid T) \cdot P(D \mid T) \cdot P(X \mid T) \cdot P(P \mid T) \cdot P(C_i \mid T) \cdot P(E) \cdot P(C_o \mid C_i, E)$$
