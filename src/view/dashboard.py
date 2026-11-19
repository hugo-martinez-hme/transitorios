"""Interfaz visual interactiva (Streamlit) para el sistema experto bayesiano RAIN."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Asegurar resolución de paquetes desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.controller.real_data_loader import DataIngestionError, RealDataLoader
from src.model.dtos import (
    AstronomicalAlert,
    DiscretizationConfig,
    VALID_STATES,
    ValidationError,
)
from src.model.transient_model import TransientModel

st.set_page_config(
    page_title="RAIN | Diagnóstico Bayesiano de Transitorios",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos refinados para tarjetas de métricas
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    div[data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 12px 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_model() -> TransientModel:
    """Instancia y cachea el DAG de 12 nodos y el motor VariableElimination."""
    return TransientModel()


@st.cache_data
def load_discretization_config() -> DiscretizationConfig:
    """Carga los umbrales configurables desde config.json."""
    return DiscretizationConfig.from_json(PROJECT_ROOT / "config.json")


def plot_horizontal_distribution(
    dist: Dict[str, float],
    title: str,
    accent: str = "#38BDF8",
    highlight_top: bool = True,
) -> plt.Figure:
    """Renderiza un gráfico horizontal limpio adaptado al tema oscuro."""
    items = sorted(dist.items(), key=lambda x: x[1])
    labels = [k.replace("_", " ") for k, _ in items]
    values = [v * 100.0 for _, v in items]
    max_val = max(values) if values else 0.0

    colors = [
        accent if (highlight_top and v == max_val) else "#334155"
        for v in values
    ]

    fig, ax = plt.subplots(figsize=(6.0, 2.8), facecolor="#0B1120")
    ax.set_facecolor("#0B1120")
    bars = ax.barh(labels, values, color=colors, height=0.58, edgecolor="none")

    ax.set_xlim(0, 112)
    ax.set_xlabel("Probabilidad posterior (%)", color="#94A3B8", fontsize=9)
    ax.set_title(title, color="#F1F5F9", fontsize=11, fontweight="bold", loc="left", pad=10)
    ax.tick_params(colors="#CBD5E1", labelsize=9)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color("#334155")

    for bar, val in zip(bars, values):
        ax.text(
            val + 1.8,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            va="center",
            color="#F8FAFC",
            fontsize=9,
            fontweight="bold" if val == max_val else "normal",
        )

    fig.tight_layout()
    return fig


def build_alert_from_sidebar(cfg: DiscretizationConfig) -> AstronomicalAlert:
    """Construye el DTO AstronomicalAlert desde la barra lateral (discreto o continuo)."""
    st.sidebar.title("Panel de Telemetría")
    mode = st.sidebar.radio(
        "Modo de entrada",
        ["Estados Discretos", "Mediciones Físicas Continuas"],
        help="Permite introducir evidencia categórica directa o magnitudes físicas reales.",
    )

    if mode == "Estados Discretos":
        st.sidebar.caption("Deja en 'No observado' cualquier sensor no disponible.")

        def _opt(label: str, node: str) -> str | None:
            choice = st.sidebar.selectbox(label, ["No observado", *VALID_STATES[node]])
            return None if choice == "No observado" else choice

        alerta = AstronomicalAlert(
            galaxia=_opt("Galaxia anfitriona", "Galaxia_Anfitriona"),
            ubicacion=_opt("Ubicación galáctica", "Ubicacion_Galactica"),
            color=_opt("Color observado (g - r)", "Color_Observado"),
            magnitud=_opt("Magnitud aparente (m_V)", "Magnitud_Aparente"),
            rayos_x=_opt("Emisión en Rayos X", "Emision_RayosX"),
            anchura_lineas=_opt("Anchura de líneas espectrales", "Anchura_Lineas"),
            curva_luz=_opt("Forma de curva de luz", "Forma_Curva_Luz"),
        )
        alerta.validar_estados()
        return alerta

    # Modo continuo con activación independiente por sensor (evidencia parcial real)
    st.sidebar.caption("Activa solo los instrumentos con lectura confirmada.")
    raw: Dict[str, Any] = {}

    gal = st.sidebar.selectbox("Galaxia anfitriona", ["No observado", *VALID_STATES["Galaxia_Anfitriona"]])
    if gal != "No observado":
        raw["galaxia"] = gal

    if st.sidebar.checkbox("Distancia al núcleo (r en kpc)", value=True):
        raw["r_kpc"] = st.sidebar.slider("r (kpc)", 0.0, 25.0, 4.5, 0.1)

    if st.sidebar.checkbox("Índice de color (g - r)", value=True):
        raw["g_minus_r"] = st.sidebar.slider("g - r (mag)", -0.8, 1.5, -0.15, 0.05)

    if st.sidebar.checkbox("Magnitud aparente (m_V)", value=True):
        raw["apparent_magnitude"] = st.sidebar.slider("m_V (mag)", 12.0, 24.0, 16.4, 0.1)

    if st.sidebar.checkbox("Rayos X + Redshift (F_X, z)", value=False):
        log_fx = st.sidebar.slider("log10(F_X [erg s^-1 cm^-2])", -17.0, -10.0, -14.5, 0.1)
        raw["x_ray_flux"] = 10.0 ** log_fx
        raw["redshift_z"] = st.sidebar.slider("Redshift (z)", 0.001, 1.0, 0.08, 0.005)

    if st.sidebar.checkbox("Velocidad / FWHM espectral (km/s)", value=False):
        raw["velocity_km_s"] = st.sidebar.slider("FWHM (km/s)", 0.0, 20000.0, 9500.0, 100.0)

    curva = st.sidebar.selectbox("Forma de curva de luz", ["No observado", *VALID_STATES["Forma_Curva_Luz"]])
    if curva != "No observado":
        raw["curva_luz"] = curva

    return AstronomicalAlert.from_continuous(raw, config=cfg)


def render_diagnosis_tab(model: TransientModel, alerta: AstronomicalAlert) -> None:
    """Tab 1: Inferencia exacta, física latente y recomendación activa por IG."""
    resultado = model.inferir(alerta)
    evidencias = alerta.to_evidence_dict()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Diagnóstico MAP", resultado.clase_predicha.replace("_", " "))
    c2.metric("Confianza Posterior", f"{resultado.confianza * 100:.1f}%")
    c3.metric("Entropía de Shannon", f"{resultado.entropia_shannon:.3f} bits")
    c4.metric("Observables Activos", f"{len(evidencias)} / 7")

    if evidencias:
        tags = " · ".join(f"`{k}: {v}`" for k, v in evidencias.items())
        st.markdown(f"**Evidencia discretizada inyectada en el DAG:** {tags}")
    else:
        st.info("Sin evidencia activa: mostrando la distribución a priori del modelo.")

    st.divider()

    col_left, col_right = st.columns([1.25, 1.0], gap="large")
    with col_left:
        fig_post = plot_horizontal_distribution(
            resultado.prob_transitorio,
            "Distribución Posterior P(Tipo_Transitorio | E)",
            accent="#38BDF8",
        )
        st.pyplot(fig_post, width="stretch")
        plt.close(fig_post)

    with col_right:
        st.markdown("#### Planificación Activa (Ganancia de Información)")
        if resultado.ganancia_info_ig:
            ig_sorted = sorted(resultado.ganancia_info_ig.items(), key=lambda x: x[1], reverse=True)
            best_var, best_ig = ig_sorted[0]
            st.success(
                f"Siguiente observación óptima: **{best_var.replace('_', ' ')}** "
                f"(IG esperada = **{best_ig:.4f} bits**)"
            )
            ig_df = pd.DataFrame(
                [{"Observable pendiente": k.replace("_", " "), "IG (bits)": round(v, 4)} for k, v in ig_sorted]
            )
            st.dataframe(ig_df, hide_index=True, width="stretch")
        else:
            st.info("Evidencia observacional completa: no quedan variables pendientes por medir.")

    st.divider()
    st.markdown("#### Inferencia Explicativa de Física Latente (Estrato 3)")
    lat_cols = st.columns(len(resultado.fisica_latente))
    for col, (var_name, dist) in zip(lat_cols, resultado.fisica_latente.items()):
        with col:
            top_state, top_prob = max(dist.items(), key=lambda x: x[1])
            st.markdown(f"**{var_name.replace('_', ' ')}**")
            st.caption(f"Estado dominante: {top_state} ({top_prob * 100:.1f}%)")
            for state, prob in dist.items():
                st.progress(min(max(prob, 0.0), 1.0), text=f"{state}: {prob * 100:.1f}%")


def render_explaining_away_tab(model: TransientModel) -> None:
    """Tab 2: Demostración interactiva de los colisionadores fotométricos."""
    st.markdown("#### Simulador Contrafactual de Colisionadores Fotométricos")
    st.markdown(
        "Fija una alerta fotométrica enrojecida o atenuada y observa cómo variar la hipótesis "
        "sobre **Extincion_Polvo** redistribuye la probabilidad sobre **Temperatura_Intrinseca**, "
        "**Luminosidad_Pico** y **Tipo_Transitorio** (*explaining away*)."
    )

    c1, c2, c3 = st.columns(3)
    color = c1.selectbox("Color observado", VALID_STATES["Color_Observado"], index=2)
    magnitud = c2.selectbox("Magnitud aparente", VALID_STATES["Magnitud_Aparente"], index=2)
    galaxia = c3.selectbox("Galaxia anfitriona", ["No observado", *VALID_STATES["Galaxia_Anfitriona"]], index=1)

    base_ev: Dict[str, str] = {"Color_Observado": color, "Magnitud_Aparente": magnitud}
    if galaxia != "No observado":
        base_ev["Galaxia_Anfitriona"] = galaxia

    rows: List[Dict[str, Any]] = []
    for dust_state in VALID_STATES["Extincion_Polvo"]:
        ev = {**base_ev, "Extincion_Polvo": dust_state}
        p_temp = model._consultar_nodo("Temperatura_Intrinseca", ev)["Alta"]
        p_lum = model._consultar_nodo("Luminosidad_Pico", ev)["Muy_Alta"]
        p_trans = model._consultar_nodo("Tipo_Transitorio", ev)
        rows.append(
            {
                "Extincion_Polvo": dust_state,
                "P(Temp = Alta)": round(p_temp, 4),
                "P(Lum = Muy_Alta)": round(p_lum, 4),
                "P(SN_Ia)": round(p_trans["SN_Ia"], 4),
                "P(SN_II)": round(p_trans["SN_II"], 4),
                "P(AGN)": round(p_trans["AGN"], 4),
                "P(Var_Estelar)": round(p_trans["Variable_Estelar"], 4),
            }
        )

    df_ea = pd.DataFrame(rows)
    st.dataframe(df_ea, hide_index=True, width="stretch")

    delta_temp = df_ea.loc[2, "P(Temp = Alta)"] - df_ea.loc[0, "P(Temp = Alta)"]
    delta_lum = df_ea.loc[2, "P(Lum = Muy_Alta)"] - df_ea.loc[0, "P(Lum = Muy_Alta)"]
    delta_snia = df_ea.loc[2, "P(SN_Ia)"] - df_ea.loc[0, "P(SN_Ia)"]

    m1, m2, m3 = st.columns(3)
    m1.metric("Delta P(Temp = Alta) [Severa vs Baja]", f"{delta_temp:+.3f}")
    m2.metric("Delta P(Lum = Muy Alta) [Severa vs Baja]", f"{delta_lum:+.3f}")
    m3.metric("Delta P(SN Ia) [Severa vs Baja]", f"{delta_snia:+.3f}")


def render_batch_tab(model: TransientModel) -> None:
    """Tab 3: Ingesta CSV por lotes y panel de métricas del repositorio."""
    st.markdown("#### Ingesta y Diagnóstico Masivo de Catálogos CSV")

    col_up, col_opt = st.columns([2, 1])
    uploaded = col_up.file_uploader(
        "Sube un dataset CSV con alertas telescópicas",
        type=["csv"],
        help="Columnas mínimas: object_id, apparent_magnitude, redshift_z, velocity_km_s, x_ray_flux, dust_extinction_ebv",
    )
    use_percentiles = col_opt.checkbox("Discretización por percentiles empíricos", value=False)

    csv_path: Path | None = None
    tmp_file: Path | None = None
    if uploaded is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tf:
            tf.write(uploaded.getvalue())
            tmp_file = Path(tf.name)
            csv_path = tmp_file
    elif (PROJECT_ROOT / "data/validation_set.csv").exists():
        st.caption("Usando el dataset local `data/validation_set.csv` (puedes subir otro CSV arriba).")
        csv_path = PROJECT_ROOT / "data/validation_set.csv"

    if csv_path is not None:
        try:
            loader = RealDataLoader(PROJECT_ROOT / "config.json", use_percentiles=use_percentiles)
            records = loader.load_dataset_csv(csv_path, drop_invalid=True)

            out_rows: List[Dict[str, Any]] = []
            for rec in records:
                res = model.inferir(rec.alert)
                out_rows.append(
                    {
                        "object_id": rec.object_id,
                        "true_class": rec.true_class or "—",
                        "pred_class": res.clase_predicha,
                        "confianza": round(res.confianza, 4),
                        "entropia_bits": round(res.entropia_shannon, 4),
                        "polvo_real": rec.dust_severity,
                        "P(Polvo=Severa)": round(res.fisica_latente["Extincion_Polvo"]["Severa"], 4),
                    }
                )

            df_res = pd.DataFrame(out_rows)
            k1, k2, k3 = st.columns(3)
            k1.metric("Objetos procesados", len(df_res))
            k2.metric("Confianza media", f"{df_res['confianza'].mean() * 100:.1f}%")
            labeled = df_res[df_res["true_class"] != "—"]
            if not labeled.empty:
                acc = (labeled["true_class"] == labeled["pred_class"]).mean()
                k3.metric("Accuracy sobre etiquetados", f"{acc * 100:.2f}%")
            else:
                k3.metric("Entropía media", f"{df_res['entropia_bits'].mean():.3f} bits")

            st.dataframe(df_res, hide_index=True, width="stretch")
            st.download_button(
                "Descargar predicciones en CSV",
                data=df_res.to_csv(index=False).encode("utf-8"),
                file_name="rain_batch_predictions.csv",
                mime="text/csv",
            )
        except (DataIngestionError, ValidationError) as exc:
            st.error(f"Error de validación en el CSV: {exc}")
        finally:
            if tmp_file is not None and tmp_file.exists():
                tmp_file.unlink()

    st.divider()
    st.markdown("#### Resultados del Último Benchmarking Guardado")
    metrics_path = PROJECT_ROOT / "reports/evaluation_metrics.json"
    cm_fig = PROJECT_ROOT / "docs/figures/confusion_matrix_normalized.png"
    ea_fig = PROJECT_ROOT / "docs/figures/explaining_away_dust_analysis.png"

    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        b1, b2, b3 = st.columns(3)
        b1.metric("Accuracy Global", f"{metrics['global_accuracy'] * 100:.2f}%")
        b2.metric("Brier Score Multiclase", f"{metrics['multiclass_brier_score']:.4f}")
        b3.metric("Muestras Evaluadas", metrics["n_evaluated"])

    fig_cols = st.columns(2)
    if cm_fig.exists():
        fig_cols[0].image(str(cm_fig), caption="Matriz de Confusión Normalizada", width="stretch")
    if ea_fig.exists():
        fig_cols[1].image(str(ea_fig), caption="Impacto del Polvo Interestelar", width="stretch")


def main() -> None:
    model = load_model()
    cfg = load_discretization_config()

    st.title("RAIN · Diagnóstico Probabilístico de Transitorios Astrofísicos")
    st.caption(
        "Red Bayesiana Causal de 12 nodos · Inferencia Exacta (VariableElimination) · "
        "Planificación Activa por Ganancia de Información"
    )

    try:
        alerta = build_alert_from_sidebar(cfg)
    except ValidationError as exc:
        st.error(f"Entrada física inválida: {exc}")
        return

    tab_diag, tab_ea, tab_batch = st.tabs(
        [
            "Diagnóstico Individual",
            "Laboratorio Explaining Away",
            "Evaluación Masiva (CSV)",
        ]
    )

    with tab_diag:
        render_diagnosis_tab(model, alerta)
    with tab_ea:
        render_explaining_away_tab(model)
    with tab_batch:
        render_batch_tab(model)


if __name__ == "__main__":
    main()