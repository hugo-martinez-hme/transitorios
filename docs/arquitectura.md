# Documento de Diseño: Sistema de Diagnóstico para Transitorios Astrofísicos (Hito 1)

## 1. Planteamiento del Problema
El sistema tiene como objetivo realizar inferencia abductiva sobre alertas astronómicas para clasificar el tipo de evento transitorio ($X_{\text{trans}}$) bajo condiciones de observación parcial o ruidosa.

## 2. Topología Propuesta del Grafo (DAG)
Se plantea una red probabilística causal de 9 variables discretas estructurada en tres niveles: contexto poblacional, hipótesis diagnóstica y manifestaciones observables (incluyendo el medio interestelar).

```text
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

## 3. Diccionario de Variables y Estados

| Variable | Tipo de Nodo | Espacio de Estados | Descripción Física |
| :--- | :--- | :--- | :--- |
| `TipoGalaxia` | Contexto / Prior | `Espiral_StarForming`, `Eliptica_Pasiva` | Densidad de formación estelar del huésped |
| `TipoTransitorio` | Hipótesis central | `SN_Ia`, `SN_II`, `AGN`, `Variable` | Clase física del fenómeno |
| `OffsetGalactico` | Manifestación | `Nuclear`, `Periferico` | Separación angular del núcleo galáctico |
| `TasaDecaimiento`| Manifestación | `Rapida`, `Lenta_Meseta` | Gradiente de la curva de luz |
| `EmisionRayosX` | Manifestación | `Detectada`, `NoDetectada` | Flujo en altas energías |
| `ComportamientoTemporal` | Manifestación | `Evento_Unico`, `Periodico` | Recurrencia histórica |
| `ColorIntrinseco` | Proceso emisor | `Azul_Caliente`, `Rojo_Frio` | Temperatura fotosférica efectiva |
| `ExtincionPolvo` | Variable ambiental | `Baja`, `Alta` | Atenuación por polvo interestelar |
| `ColorObservado` | Evidencia final | `Azul_Aparente`, `Rojo_Aparente` | Índice de color medido por el telescopio |

## 4. Fundamentos Teóricos Incorporados
* **Incompatibilidad de colapso de núcleo en elípticas:** Las supernovas de colapso ($\text{SN\_II}$) provienen de estrellas masivas de vida corta; su probabilidad en galaxias elípticas pasivas se modela tendiendo a cero: $P(\text{SN\_II} \mid \text{Eliptica}) \approx 0$.
* **Localización nuclear de AGN:** La actividad de acreción supermasiva se restringe geométricamente al núcleo galáctico: $P(\text{Nuclear} \mid \text{AGN}) \approx 1$.
* **Estructura en V (*Collider*):** El color aparente depende conjuntamente de la emisión física y de la extinción en la línea de visión, modelando el fenómeno de *explaining away*.

## 5. Estado del Proyecto
* **Hito 1 (Actual):**
  * Definición formal del grafo acíclico dirigido (DAG).
  * Construcción de las tablas de probabilidad condicional (CPTs) y verificación de consistencia.
  * Validación del motor de inferencia con casos preliminares.
* **Hito 2 (Próximo):**
  * Calibración fina con distribuciones empíricas.
  * Análisis de sensibilidad ante observaciones incompletas o contradictorias.
