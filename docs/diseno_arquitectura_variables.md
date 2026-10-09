# Especificación Técnica: Arquitectura del Sistema y Diseño de la Red Bayesiana

**Materia:** Razonamiento con Incertidumbre (RAIN) - Grado en Inteligencia Artificial  
**Autores:** Anxo Grandal Lama y Hugo Martínez Estévez  
**Estado:** Documento formal de arquitectura y modelado causal (Hito Sesiones 5 a 7)

---

## 1. Arquitectura del Software: Patrón MVC Modular

Para cumplir con la separación de responsabilidades y permitir la ejecución local desacoplada, la aplicación se estructura bajo el patrón **Modelo-Vista-Controlador (MVC)** organizado en 5 clases:

```mermaid
classDiagram
    direction TB

    class AstronomicalAlert {
        +galaxia: str
        +ubicacion: str
        +color: str
        +rayos_x: str
        +velocidad: str
        +curva_luz: str
        +polvo: str
        +to_evidence_dict() dict
        +validar_estados() bool
    }

    class DiagnosisResult {
        +probabilidades: dict
        +clase_predicha: str
        +confianza: float
        +formatear_informe() str
    }

    class NetworkBuilder {
        +definir_nodos_aristas() BayesianNetwork
        +cargar_cpts() list
        +ensamblar_red() BayesianNetwork
    }

    class TransientModel {
        -red: BayesianNetwork
        -motor_inferencia: VariableElimination
        +inferir(alerta: AstronomicalAlert) DiagnosisResult
        +obtener_espacios_estados() dict
    }

    class DiagnosisController {
        -modelo: TransientModel
        -vista: ConsoleView
        +iniciar()
        +procesar_evento_diagnostico(datos_crudos: dict)
    }

    class ConsoleView {
        +mostrar_menu_principal()
        +solicitar_evidencias_usuario() dict
        +mostrar_diagnostico(resultado: DiagnosisResult)
        +mostrar_error(mensaje: str)
    }

    NetworkBuilder ..> TransientModel : Construye e inyecta la red
    ConsoleView --> DiagnosisController : 1. Notifica evento de usuario
    DiagnosisController --> AstronomicalAlert : 2. Instancia y valida entrada
    DiagnosisController --> TransientModel : 3. Solicita inferir(alerta)
    TransientModel --> DiagnosisResult : 4. Devuelve resultado tipado
    DiagnosisController --> ConsoleView : 5. Pasa resultado a mostrar_diagnostico()
```

### 1.1. Responsabilidades y Flujo de Interacción
1. **Entrada de datos (`ConsoleView`):** La vista captura las observaciones del usuario (alertas telescópicas reales o simuladas) y las envía al controlador sin interactuar con la lógica bayesiana.
2. **Validación y mediación (`DiagnosisController` y `AstronomicalAlert`):** El controlador recibe los datos crudos, valida que los estados observados pertenezcan a los dominios físicos permitidos instanciando un objeto tipado `AstronomicalAlert`, y solicita el diagnóstico.
3. **Construcción desacoplada (`NetworkBuilder`):** Aísla la definición matemática y topológica de la red en `pgmpy`, evitando sobrecargar el modelo con definiciones tabulares estáticas.
4. **Motor de inferencia (`TransientModel`):** Resuelve el cálculo probabilístico exacto mediante `VariableElimination` sobre la evidencia observada y empaqueta la distribución posterior en un objeto `DiagnosisResult`.
5. **Presentación de resultados:** El controlador recibe `DiagnosisResult` y le ordena a la vista mostrar el informe ordenado de probabilidades.

---

## 2. Especificación Formal de Variables y Espacios de Estados

El dominio modela **9 variables discretas**, exhaustivas y mutuamente excluyentes, categorizadas según su función dentro del sistema de diagnóstico:

| Variable | Rol en la Red | Espacio de Estados Discretos | Justificación Física / Dominio Astrofísico |
| :--- | :--- | :--- | :--- |
| **`Tipo_Transitorio`** | **Diagnóstico (Objetivo)** | `{SN_Ia, SN_II, AGN, Variable_Estelar}` | Fenómeno físico real subyacente que se desea inferir. |
| **`Galaxia_Anfitriona`** | Contexto Causal (Prior) | `{Espiral, Eliptica, Irregular}` | Entorno galáctico; las galaxias elípticas carecen de gas para colapso gravitatorio masivo (probabilidad nula de SN II). |
| **`Ubicacion_Galactica`** | Causal intermedia | `{Nuclear, Brazo_Espiral, Halo}` | Los núcleos galácticos activos (AGN) se ubican estrictamente en el núcleo; las SN II aparecen en brazos espirales de formación. |
| **`Temperatura_Intrinseca`** | Causal física | `{Alta, Media, Baja}` | Mecanismo térmico de emisión emitido en la fuente antes de sufrir dispersión interestelar. |
| **`Extincion_Polvo`** | Ruido de línea de visión | `{Baja, Moderada, Severa}` | Atenuación física provocada por la dispersión del polvo interestelar entre la fuente y el observador. |
| **`Color_Observado`** | Observable (Colisionador) | `{Azul, Neutro, Rojo}` | Efecto conjunto de la temperatura intrínseca modulada por el enrojecimiento del polvo interestelar. |
| **`Emision_RayosX`** | Observable alta energía | `{Intensa, Debil, Nula}` | Distintivo de procesos de acreción en pozos gravitatorios profundos (agujeros negros supermasivos en AGN). |
| **`Velocidad_Expansion`** | Observable cinemático | `{Muy_Alta, Moderada, Baja_Nula}` | Ensanchamiento Doppler en líneas espectrales debido a la onda de choque expulsada a miles de km/s en supernovas. |
| **`Forma_Curva_Luz`** | Observable temporal | `{Decaimiento_Rapido, Meseta, Estocastica}` | Evolución temporal del brillo (caída lineal rápida en SN Ia, meseta sostenida en SN II, variabilidad estocástica en AGN). |

---

## 3. Topología Causal y Arquitectura de la Red Bayesiana (DAG)

El grafo acíclico dirigido sigue una orientación estricta de causa física a efecto observable:

```mermaid
flowchart TD
    %% Nodos
    G["Galaxia_Anfitriona<br><i>(Contexto / Prior)</i>"]
    T["<b>Tipo_Transitorio</b><br><i>(Objetivo Diagnóstico)</i>"]
    
    U["Ubicacion_Galactica<br><i>(Observable Espacial)</i>"]
    X["Emision_RayosX<br><i>(Observable Alta Energía)</i>"]
    V["Velocidad_Expansion<br><i>(Observable Cinemático)</i>"]
    L["Forma_Curva_Luz<br><i>(Observable Temporal)</i>"]
    
    Temp["Temperatura_Intrinseca<br><i>(Física Latente)</i>"]
    Polvo["Extincion_Polvo<br><i>(Ruido Línea de Visión)</i>"]
    C["<b>Color_Observado</b><br><i>(Observable / Collider)</i>"]

    %% Enlaces Causales
    G --> T
    T --> U
    T --> X
    T --> V
    T --> L
    T --> Temp

    %% Estructura en V (Collider)
    Temp --> C
    Polvo --> C

    %% Estilos visuales
    style T fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#000
    style C fill:#ef4444,stroke:#b91c1c,stroke-width:2px,color:#fff
    style G fill:#3b82f6,stroke:#1d4ed8,stroke-width:1px,color:#fff
    style Polvo fill:#64748b,stroke:#334155,stroke-width:1px,color:#fff
    style Temp fill:#8b5cf6,stroke:#6d28d9,stroke-width:1px,color:#fff
    style U fill:#10b981,stroke:#047857,stroke-width:1px,color:#fff
    style X fill:#10b981,stroke:#047857,stroke-width:1px,color:#fff
    style V fill:#10b981,stroke:#047857,stroke-width:1px,color:#fff
    style L fill:#10b981,stroke:#047857,stroke-width:1px,color:#fff
```

---

## 4. Factorización de la Distribución Conjunta

Aplicando la regla de la cadena para redes bayesianas, la distribución de probabilidad conjunta global sobre las 9 variables se factoriza como:

$$P(G, T, U, \theta, E, C, X, V, L) = P(G) \cdot P(E) \cdot P(T \mid G) \cdot P(U \mid T) \cdot P(\theta \mid T) \cdot P(X \mid T) \cdot P(V \mid T) \cdot P(L \mid T) \cdot P(C \mid \theta, E)$$

Donde:
* $G$: `Galaxia_Anfitriona`
* $E$: `Extincion_Polvo`
* $T$: `Tipo_Transitorio` (nodo diagnóstico)
* $U$: `Ubicacion_Galactica`
* $\theta$: `Temperatura_Intrinseca`
* $C$: `Color_Observado`
* $X$: `Emision_RayosX`
* $V$: `Velocidad_Expansion`
* $L$: `Forma_Curva_Luz`

---

## 5. Análisis de Independencias Condicionales y Estructuras Causales

* **Estructura en V (*Collider*) y *Explaining Away*:** La confluencia causal $\theta \rightarrow C \leftarrow E$ representa una estructura de colisión. Incondicionalmente, la temperatura física de la fuente y la presencia de polvo interestelar son estocásticamente independientes ($E \perp \theta$). Al condicionar sobre la evidencia observada del colisionador ($C = \text{Rojo}$), las variables parentales se vuelven dependientes: conocer la presencia de alta extinción por polvo ($E = \text{Severa}$) reduce la necesidad de atribuir el color rojo a una temperatura baja, recuperando una alta probabilidad posterior de que la fuente sea intrínsecamente caliente ($\theta = \text{Alta}$).
* **Independencia Condicional de Observables:** Condicionado al tipo real de evento astronómico ($T$), los observables directos son mutuamente independientes entre sí:
  $$(X \perp V \perp L \perp U \perp \theta \mid T)$$
  Esta propiedad reduce la complejidad combinatoria en las CPTs y garantiza la viabilidad computacional de la inferencia exacta con el algoritmo de eliminación de variables.