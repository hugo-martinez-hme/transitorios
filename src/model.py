from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD

def construir_red_transitorios() -> DiscreteBayesianNetwork:
    """
    Construye y valida la red bayesiana para el diagnóstico de transitorios astrofísicos.
    Incluye contexto de galaxia huésped y estructura en V (collider) para extinción por polvo.
    """
    modelo = DiscreteBayesianNetwork([
        # Dependencia contextual
        ('TipoGalaxia', 'TipoTransitorio'),
        
        # Manifestaciones observables directas
        ('TipoTransitorio', 'OffsetGalactico'),
        ('TipoTransitorio', 'TasaDecaimiento'),
        ('TipoTransitorio', 'EmisionRayosX'),
        ('TipoTransitorio', 'ComportamientoTemporal'),
        ('TipoTransitorio', 'ColorIntrinseco'),
        
        # Estructura en V (Collider): Color Observado depende de la emisión intrínseca y del medio
        ('ColorIntrinseco', 'ColorObservado'),
        ('ExtincionPolvo', 'ColorObservado')
    ])

    # 1. Tipo de Galaxia Huésped (Prior contextual)
    cpd_galaxia = TabularCPD(
        variable='TipoGalaxia',
        variable_card=2,
        values=[[0.65], [0.35]],
        state_names={'TipoGalaxia': ['Espiral_StarForming', 'Eliptica_Pasiva']}
    )

    # 2. Tipo de Transitorio condicionado por el entorno galáctico
    # Las supernovas por colapso (SN_II) requieren estrellas masivas jóvenes (inexistentes en elípticas pasivas)
    cpd_transitorio = TabularCPD(
        variable='TipoTransitorio',
        variable_card=4,
        values=[
            [0.35, 0.65],    # SN_Ia (progenitores viejos o intermedios en ambas)
            [0.40, 0.001],   # SN_II (prácticamente nula en elípticas)
            [0.10, 0.15],    # AGN (agujeros negros supermasivos)
            [0.15, 0.199]    # Variable (estrellas variables de diversa población)
        ],
        evidence=['TipoGalaxia'],
        evidence_card=[2],
        state_names={
            'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable'],
            'TipoGalaxia': ['Espiral_StarForming', 'Eliptica_Pasiva']
        }
    )

    # 3. Offset respecto al centro galáctico
    # AGN reside invariablemente en el núcleo; supernovas predominan en el disco/periferia
    cpd_offset = TabularCPD(
        variable='OffsetGalactico',
        variable_card=2,
        values=[
            [0.05, 0.02, 0.99, 0.20],  # Nuclear
            [0.95, 0.98, 0.01, 0.80]   # Periferico
        ],
        evidence=['TipoTransitorio'],
        evidence_card=[4],
        state_names={
            'OffsetGalactico': ['Nuclear', 'Periferico'],
            'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']
        }
    )

    # 4. Tasa de decaimiento fotométrico
    # SN_Ia cae con rapidez típica; SN_II (tipo IIP) exhibe meseta; AGN presenta variación lenta/estocástica
    cpd_decaimiento = TabularCPD(
        variable='TasaDecaimiento',
        variable_card=2,
        values=[
            [0.85, 0.20, 0.10, 0.50],  # Rapida
            [0.15, 0.80, 0.90, 0.50]   # Lenta_Meseta
        ],
        evidence=['TipoTransitorio'],
        evidence_card=[4],
        state_names={
            'TasaDecaimiento': ['Rapida', 'Lenta_Meseta'],
            'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']
        }
    )

    # 5. Emisión de Rayos X de alta energía
    # Discos de acreción en AGN generan emisión sincrotrón y térmica de rayos X sistemática
    cpd_xray = TabularCPD(
        variable='EmisionRayosX',
        variable_card=2,
        values=[
            [0.02, 0.05, 0.85, 0.01],  # Detectada
            [0.98, 0.95, 0.15, 0.99]   # NoDetectada
        ],
        evidence=['TipoTransitorio'],
        evidence_card=[4],
        state_names={
            'EmisionRayosX': ['Detectada', 'NoDetectada'],
            'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']
        }
    )

    # 6. Comportamiento temporal histórico
    # Las supernovas son cataclismos terminales únicos; estrellas variables son periódicas
    cpd_temporal = TabularCPD(
        variable='ComportamientoTemporal',
        variable_card=2,
        values=[
            [0.99, 0.99, 0.30, 0.05],  # Evento_Unico
            [0.01, 0.01, 0.70, 0.95]   # Periodico
        ],
        evidence=['TipoTransitorio'],
        evidence_card=[4],
        state_names={
            'ComportamientoTemporal': ['Evento_Unico', 'Periodico'],
            'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']
        }
    )

    # 7. Color intrínseco (Temperatura termodinámica de emisión)
    # Gas inicial a alta temperatura (>10.000 K) emite en azul; variables frías dominan en rojo
    cpd_color_int = TabularCPD(
        variable='ColorIntrinseco',
        variable_card=2,
        values=[
            [0.75, 0.85, 0.80, 0.15],  # Azul_Caliente
            [0.25, 0.15, 0.20, 0.85]   # Rojo_Frio
        ],
        evidence=['TipoTransitorio'],
        evidence_card=[4],
        state_names={
            'ColorIntrinseco': ['Azul_Caliente', 'Rojo_Frio'],
            'TipoTransitorio': ['SN_Ia', 'SN_II', 'AGN', 'Variable']
        }
    )

    # 8. Extinción por polvo interestelar (Variable ambiental independiente)
    cpd_polvo = TabularCPD(
        variable='ExtincionPolvo',
        variable_card=2,
        values=[[0.70], [0.30]],
        state_names={'ExtincionPolvo': ['Baja', 'Alta']}
    )

    # 9. Color Observado (Estructura en V)
    # El polvo absorbe longitudes de onda cortas; una fuente caliente puede verse roja por enrojecimiento
    cpd_color_obs = TabularCPD(
        variable='ColorObservado',
        variable_card=2,
        values=[
            # Intrinseco=Azul (Baja, Alta) | Intrinseco=Rojo (Baja, Alta)
            [0.98, 0.20, 0.02, 0.01],  # Azul_Aparente
            [0.02, 0.80, 0.98, 0.99]   # Rojo_Aparente
        ],
        evidence=['ColorIntrinseco', 'ExtincionPolvo'],
        evidence_card=[2, 2],
        state_names={
            'ColorObservado': ['Azul_Aparente', 'Rojo_Aparente'],
            'ColorIntrinseco': ['Azul_Caliente', 'Rojo_Frio'],
            'ExtincionPolvo': ['Baja', 'Alta']
        }
    )

    modelo.add_cpds(
        cpd_galaxia, cpd_transitorio, cpd_offset, cpd_decaimiento,
        cpd_xray, cpd_temporal, cpd_color_int, cpd_polvo, cpd_color_obs
    )
    
    assert modelo.check_model(), "Error: el modelo contiene inconsistencias de normalización o arcos"
    return modelo
