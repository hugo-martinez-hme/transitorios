# Planificación del Proyecto: Diagnóstico de Transitorios Astrofísicos

**Materia:** Razonamiento con Incertidumbre (RAIN) - Grado en Inteligencia Artificial  
**Autores:** Anxo Grandal Lama y Hugo Martínez Estévez

## 1. Introducción

En la astronomía observacional contemporánea, los sondeos telescópicos continuos detectan miles de eventos astronómicos transitorios (fenómenos de brillo variable en escalas de tiempo cortas, como explosiones de supernovas, actividad de núcleos galácticos activos o estrellas variables). Determinar la naturaleza física real de estos eventos resulta crítico para la astrofísica moderna, pero plantea un desafío significativo: los datos se recopilan bajo condiciones de información incompleta, presencia de ruido observacional y alteraciones físicas en la línea de visión (como la absorción lumínica causada por el polvo interestelar). Este proyecto aborda la necesidad de interpretar estas alertas telescópicas, caracterizando el origen de los fenómenos observados aun cuando la evidencia disponible sea escasa o imperfecta.

## 2. Objetivos del Proyecto

### 2.1. Objetivo General
Clasificar e inferir la naturaleza intrínseca de eventos astronómicos transitorios a partir de datos observacionales sujetos a incertidumbre, ruido y cobertura informativa parcial.

### 2.2. Subobjetivos
*   **Formalización del dominio astrofísico:** Identificar y estructurar las características físicas de los transitorios y sus manifestaciones observacionales clave (entorno galáctico, color, cinemática y emisiones de alta energía).
*   **Modelado de dependencias causales:** Definir formalmente los vínculos directos e independencias condicionales que conectan la física de los eventos con las mediciones telescópicas.
*   **Inferencia ante evidencia incompleta:** Deducir el tipo de fenómeno astrofísico observado aun cuando solo se disponga de observaciones parciales o preliminares.
*   **Validación frente a escenarios complejos:** Evaluar la solidez del razonamiento en casos observacionales ambiguos, como la presencia de atenuación por polvo interestelar o alertas con baja relación señal-ruido.

## 3. Metodología de Desarrollo: CommonKADS en Dos Incrementos

Para el desarrollo se adopta la metodología **CommonKADS**, estructurada en un ciclo de vida iterativo en **dos incrementos**:

*   **Justificación:** El proyecto se fundamenta en estructurar **conocimiento experto** astrofísico para resolver un problema de razonamiento bajo incertidumbre. CommonKADS permite desacoplar la conceptualización cualitativa del problema (variables y estructura causal) de la parametrización cuantitativa antes de abordar la programación.
*   **Descarte de alternativas:** Se descarta *CRISP-DM* al no tratarse de minería inductiva sobre un gran conjunto de datos tabulares, y *Scrum* debido a que los ciclos de sprints no se ajustan a las dos entregas académicas prefijadas.
*   **Articulación en dos incrementos:**
    *   **Incremento 1 (Prototipo funcional - S9):** Modelado del núcleo causal básico (tipo de galaxia, clase de transitorio, cinemática y rayos X) con inferencia preliminar demostrable.
    *   **Incremento 2 (Sistema final - S14):** Ampliación con inter-causalidad compleja (efecto de extinción por polvo interestelar y *explaining away*), pruebas de sensibilidad y memoria técnica completa.

## 4. Desglose de Tareas en Dos Fases (Incrementos)

El desarrollo técnico se abordará de forma conjunta (50/50) distribuyendo las tareas a lo largo de las dos fases del proyecto:

*   **Fase 1: Incremento 1 (Prototipo Funcional)**
    *   Definición formal del catálogo de variables principales y sus espacios de estados discretos.
    *   Diseño y justificación del grafo causal nuclear y sus independencias condicionales.
    *   Estimación preliminar y volcado de las tablas de probabilidad condicional base.
    *   Implementación del núcleo computacional y verificación de consultas de inferencia iniciales.
    *   Redacción del Documento de Arquitectura y preparación del prototipo para evaluación.
*   **Fase 2: Incremento 2 (Sistema Final y Validación)**
    *   Ampliación de dependencias causales complejas (incorporación de absorción por polvo interestelar y estructuras de colisión/*explaining away*).
    *   Refinamiento cuantitativo de las distribuciones de probabilidad mediante literatura astrofísica.
    *   Diseño y ejecución de baterías de prueba de diagnóstico con alertas simuladas.
    *   Elaboración del índice, redacción de la memoria técnica y preparación de la defensa final.

## 5. Cronograma Detallado y Entregables (Evaluación Continua)

El desarrollo del proyecto se estructura en el siguiente calendario de trabajo conjunto (50/50), culminando cada fase en su respectivo hito de incremento:

| Semana | Hito / Tarea Principal (50/50) | Entregable Oficial |
| :--- | :--- | :--- |
| **5 - 9 Oct** | Definición de las variables principales y sus espacios de estados. | Revisión del estado de avance |
| **19 - 23 Oct** | Análisis de independencias, dependencias directas y estructuras causales. | Revisión del estado de avance |
| **26 - 30 Oct** | Justificación del grafo causal y factorización de la distribución conjunta. | **Documento de Arquitectura** |
| **2 - 6 Nov** | Configuración del entorno de desarrollo e implementación de probabilidades base. | Revisión del estado de avance |
| **9 - 13 Nov** | Modelo instanciado en código con inferencias funcionales demostrables. | **Fin del incremento 1: Prototipo** |
| **16 - 20 Nov** | Ajuste fino de probabilidades y ampliación del modelo (extinción por polvo). | Revisión del estado de avance |
| **23 - 27 Nov** | Propuesta del índice y secciones de la memoria técnica con el profesor. | **Estructura de la Memoria** |
| **30 Nov - 4 Dic** | Redacción de la memoria, pruebas de robustez y preparación de la presentación. | Revisión del estado de avance |
| **7 - 18 Dic** | Presentación, demostración del software y ronda de preguntas. | **Defensa del proyecto** |
| **18 Dic** | Código completo final (`pgmpy`) y entrega definitiva de la memoria técnica. | **Fin del incremento 2: Sistema final y memoria** |

## 6. Diagrama de Gantt

![Diagrama de Gantt](diagrama_gantt_planificacion.png)