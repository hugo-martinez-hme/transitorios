"""Pipeline de validación masiva, benchmarking y auditoría de Explaining Away para RAIN."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.controller.real_data_loader import RealDataLoader, TransientRecord
from src.model.dtos import VALID_STATES
from src.model.transient_model import TransientModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("RAIN.BatchEvaluation")

CLASSES: List[str] = list(VALID_STATES["Tipo_Transitorio"])


def compute_confusion_matrix(
    y_true: List[str],
    y_pred: List[str],
    labels: List[str],
) -> Tuple[np.ndarray, np.ndarray]:
    """Calcula la matriz de confusión cruda $C$ y normalizada por filas $\\tilde{C}$."""
    n = len(labels)
    idx = {label: i for i, label in enumerate(labels)}
    cm_raw = np.zeros((n, n), dtype=int)
    for yt, yp in zip(y_true, y_pred):
        cm_raw[idx[yt], idx[yp]] += 1

    row_sums = cm_raw.sum(axis=1, keepdims=True)
    cm_norm = np.divide(
        cm_raw.astype(float),
        row_sums,
        out=np.zeros_like(cm_raw, dtype=float),
        where=row_sums != 0,
    )
    return cm_raw, cm_norm


def compute_classification_metrics(
    cm_raw: np.ndarray,
    labels: List[str],
) -> Dict[str, Any]:
    """Calcula Accuracy global, Precision, Recall y F1-Score por clase y macro/weighted."""
    total = int(cm_raw.sum())
    accuracy = float(np.trace(cm_raw) / total) if total > 0 else 0.0

    per_class: Dict[str, Dict[str, float | int]] = {}
    precisions, recalls, f1s, supports = [], [], [], []

    for i, label in enumerate(labels):
        tp = int(cm_raw[i, i])
        fp = int(cm_raw[:, i].sum() - tp)
        fn = int(cm_raw[i, :].sum() - tp)
        support = int(cm_raw[i, :].sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "support": support,
        }
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        supports.append(support)

    weights = np.array(supports, dtype=float)
    w_sum = weights.sum()
    return {
        "accuracy": round(accuracy, 4),
        "macro_avg": {
            "precision": round(float(np.mean(precisions)), 4),
            "recall": round(float(np.mean(recalls)), 4),
            "f1_score": round(float(np.mean(f1s)), 4),
        },
        "weighted_avg": {
            "precision": round(float(np.dot(precisions, weights) / w_sum), 4) if w_sum > 0 else 0.0,
            "recall": round(float(np.dot(recalls, weights) / w_sum), 4) if w_sum > 0 else 0.0,
            "f1_score": round(float(np.dot(f1s, weights) / w_sum), 4) if w_sum > 0 else 0.0,
        },
        "per_class": per_class,
    }


def evaluate_explaining_away(
    model: TransientModel,
    records: List[TransientRecord],
    predictions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    r"""Cuantifica el fenómeno de Explaining Away en los colisionadores fotométricos.

    1) Estratifica precisión, entropía posterior y $P(\\text{Extincion\_Polvo}=\\text{Severa} \\mid E)$
       por severidad real de polvo $E(B-V)$.
    2) Realiza un análisis contrafactual exacto sobre los objetos con evidencia fotométrica
       enrojecida (`Color_Observado == 'Rojo'`) o atenuada (`Magnitud_Aparente == 'Debil'`),
       midiendo el desplazamiento probabilístico $\\Delta P_{\\text{EA}}$ en la temperatura
       intrínseca y en la hipótesis `SN_Ia` al condicionar sobre polvo `Severa` vs `Baja`.
    """
    by_dust: Dict[str, List[Dict[str, Any]]] = {"Baja": [], "Moderada": [], "Severa": []}
    for entry in predictions:
        by_dust[entry["dust_severity"]].append(entry)

    stratified: Dict[str, Any] = {}
    for severity, items in by_dust.items():
        if not items:
            stratified[severity] = {"count": 0}
            continue
        acc = float(np.mean([1.0 if x["y_true"] == x["y_pred"] else 0.0 for x in items]))
        mean_conf = float(np.mean([x["confidence"] for x in items]))
        mean_ent = float(np.mean([x["entropy"] for x in items]))
        mean_p_dust_severe = float(np.mean([x["p_dust_severa"] for x in items]))
        stratified[severity] = {
            "count": len(items),
            "accuracy": round(acc, 4),
            "mean_confidence": round(mean_conf, 4),
            "mean_shannon_entropy_bits": round(mean_ent, 4),
            "mean_inferred_p_dust_severa": round(mean_p_dust_severe, 4),
        }

    # Contrafactual sobre colisionadores fotométricos:
    # Temperatura_Intrinseca -> Color_Observado <- Extincion_Polvo
    # Luminosidad_Pico       -> Magnitud_Aparente <- Extincion_Polvo
    delta_temp_alta: List[float] = []
    delta_lum_muy_alta: List[float] = []
    delta_sn_ia: List[float] = []

    for rec in records:
        ev = rec.alert.to_evidence_dict()
        if ev.get("Color_Observado") != "Rojo" and ev.get("Magnitud_Aparente") != "Debil":
            continue

        ev_baja = {**ev, "Extincion_Polvo": "Baja"}
        ev_severa = {**ev, "Extincion_Polvo": "Severa"}

        p_temp_baja = model._consultar_nodo("Temperatura_Intrinseca", ev_baja)["Alta"]
        p_temp_sev = model._consultar_nodo("Temperatura_Intrinseca", ev_severa)["Alta"]
        delta_temp_alta.append(p_temp_sev - p_temp_baja)

        p_lum_baja = model._consultar_nodo("Luminosidad_Pico", ev_baja)["Muy_Alta"]
        p_lum_sev = model._consultar_nodo("Luminosidad_Pico", ev_severa)["Muy_Alta"]
        delta_lum_muy_alta.append(p_lum_sev - p_lum_baja)

        p_snia_baja = model._consultar_nodo("Tipo_Transitorio", ev_baja)["SN_Ia"]
        p_snia_sev = model._consultar_nodo("Tipo_Transitorio", ev_severa)["SN_Ia"]
        delta_sn_ia.append(p_snia_sev - p_snia_baja)

    return {
        "stratified_by_true_dust": stratified,
        "photometric_collider_counterfactual": {
            "evaluated_red_or_faint_objects": len(delta_temp_alta),
            "mean_delta_p_temp_alta_severa_vs_baja": (
                round(float(np.mean(delta_temp_alta)), 4) if delta_temp_alta else 0.0
            ),
            "mean_delta_p_lum_muy_alta_severa_vs_baja": (
                round(float(np.mean(delta_lum_muy_alta)), 4) if delta_lum_muy_alta else 0.0
            ),
            "mean_delta_p_sn_ia_severa_vs_baja": (
                round(float(np.mean(delta_sn_ia)), 4) if delta_sn_ia else 0.0
            ),
        },
    }


def plot_confusion_matrix(
    cm_raw: np.ndarray,
    cm_norm: np.ndarray,
    labels: List[str],
    output_path: Path,
) -> None:
    """Genera y guarda el mapa de calor de la matriz de confusión con Matplotlib puro."""
    fig, ax = plt.subplots(figsize=(8, 6.5))
    im = ax.imshow(cm_norm, interpolation="nearest", cmap="Blues", vmin=0.0, vmax=1.0)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Proporción normalizada (Recall)")

    ax.set(
        xticks=np.arange(len(labels)),
        yticks=np.arange(len(labels)),
        xticklabels=labels,
        yticklabels=labels,
        title="RAIN: Matriz de Confusión Normalizada (Inferencia Exacta)",
        ylabel="Clase Real (Ground Truth)",
        xlabel="Clase Predicha (MAP)",
    )
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right", rotation_mode="anchor")

    for i in range(len(labels)):
        for j in range(len(labels)):
            val = cm_norm[i, j]
            cnt = cm_raw[i, j]
            color = "white" if val > 0.55 else "black"
            ax.text(j, i, f"{val:.2f}\n(n={cnt})", ha="center", va="center", color=color, fontsize=10)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_explaining_away_summary(ea_report: Dict[str, Any], output_path: Path) -> None:
    """Genera un gráfico comparativo del impacto del polvo interestelar en la inferencia."""
    strat = ea_report["stratified_by_true_dust"]
    severities = ["Baja", "Moderada", "Severa"]
    accuracies = [strat[s].get("accuracy", 0.0) for s in severities]
    entropies = [strat[s].get("mean_shannon_entropy_bits", 0.0) for s in severities]

    x = np.arange(len(severities))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(7.5, 5))
    bars1 = ax1.bar(x - width / 2, accuracies, width, label="Accuracy", color="#2b5c8f")
    ax1.set_ylabel("Accuracy", color="#2b5c8f")
    ax1.set_ylim(0.0, 1.1)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"Polvo {s}" for s in severities])
    ax1.set_title("Impacto de la Extinción por Polvo (Colisionadores Fotométricos)")

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width / 2, entropies, width, label="Entropía Shannon (bits)", color="#d97724")
    ax2.set_ylabel("Entropía Posterior Media (bits)", color="#d97724")
    ax2.set_ylim(0.0, 2.2)

    for b in bars1:
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.02, f"{b.get_height():.2f}", ha="center")
    for b in bars2:
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.04, f"{b.get_height():.2f}", ha="center")

    fig.legend(loc="upper right", bbox_to_anchor=(0.88, 0.88))
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def generate_realistic_validation_dataset(path: Path, n_samples: int = 120, seed: int = 42) -> None:
    """Genera un dataset sintético físicamente coherente con los 4 tipos de transitorios."""
    rng = np.random.default_rng(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []

    for i in range(n_samples):
        cls = CLASSES[i % len(CLASSES)]
        ebv = float(rng.choice([rng.uniform(0.01, 0.08), rng.uniform(0.15, 0.40), rng.uniform(0.60, 1.20)]))
        a_v = 3.1 * ebv  # Extinción visual A_V = R_V * E(B-V)

        if cls == "SN_Ia":
            galaxia = str(rng.choice(["Eliptica", "Espiral"], p=[0.6, 0.4]))
            r_kpc = float(rng.uniform(3.0, 20.0))
            z = float(rng.uniform(0.02, 0.12))
            m_v = float(rng.uniform(15.2, 16.8) + a_v)
            g_minus_r = float(rng.uniform(-0.35, -0.05) + 0.9 * ebv)
            vel = float(rng.uniform(8000.0, 15000.0))
            fx = float(rng.uniform(1e-17, 5e-16))
            curva = "Decaimiento_Rapido"
        elif cls == "SN_II":
            galaxia = str(rng.choice(["Espiral", "Irregular"], p=[0.75, 0.25]))
            r_kpc = float(rng.uniform(2.0, 12.0))
            z = float(rng.uniform(0.01, 0.09))
            m_v = float(rng.uniform(16.8, 18.8) + a_v)
            g_minus_r = float(rng.uniform(-0.1, 0.25) + 0.9 * ebv)
            vel = float(rng.uniform(4000.0, 9000.0))
            fx = float(rng.uniform(1e-15, 5e-14))
            curva = "Meseta"
        elif cls == "AGN":
            galaxia = str(rng.choice(["Espiral", "Eliptica"], p=[0.55, 0.45]))
            r_kpc = float(rng.uniform(0.05, 0.8))
            z = float(rng.uniform(0.08, 0.45))
            m_v = float(rng.uniform(16.0, 19.0) + 0.6 * a_v)
            g_minus_r = float(rng.uniform(-0.3, 0.2) + 0.7 * ebv)
            vel = float(rng.uniform(3500.0, 10000.0))
            fx = float(rng.uniform(5e-13, 2e-11))
            curva = "Estocastica"
        else:  # Variable_Estelar
            galaxia = str(rng.choice(["Espiral", "Irregular"], p=[0.7, 0.3]))
            r_kpc = float(rng.uniform(2.0, 14.0))
            z = float(rng.uniform(0.0001, 0.002))
            m_v = float(rng.uniform(19.0, 22.0) + 0.5 * a_v)
            g_minus_r = float(rng.uniform(0.3, 1.0) + 0.5 * ebv)
            vel = float(rng.uniform(50.0, 800.0))
            fx = float(rng.uniform(1e-17, 1e-15))
            curva = "Estocastica"

        rows.append(
            {
                "object_id": f"ZTF26_{i:04d}",
                "apparent_magnitude": round(m_v, 3),
                "redshift_z": round(z, 5),
                "velocity_km_s": round(vel, 1),
                "x_ray_flux": fx,
                "dust_extinction_ebv": round(ebv, 4),
                "galaxia": galaxia,
                "r_kpc": round(r_kpc, 3),
                "g_minus_r": round(g_minus_r, 3),
                "curva_luz": curva,
                "true_class": cls,
            }
        )

    pd.DataFrame(rows).to_csv(path, index=False)
    logger.info("Dataset sintético de validación generado en '%s' (%d objetos).", path, n_samples)


def run_evaluation(
    dataset_path: Path = Path("data/validation_set.csv"),
    config_path: Path = Path("config.json"),
) -> Dict[str, Any]:
    """Ejecuta el pipeline completo de evaluación y exporta reportes y figuras."""
    reports_dir = Path("reports")
    figures_dir = Path("docs/figures")
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    if not dataset_path.exists():
        generate_realistic_validation_dataset(dataset_path)

    loader = RealDataLoader(config_path=config_path)
    records = loader.load_dataset_csv(dataset_path)

    model = TransientModel()
    y_true: List[str] = []
    y_pred: List[str] = []
    brier_scores: List[float] = []
    prediction_details: List[Dict[str, Any]] = []

    logger.info("Ejecutando VariableElimination sobre %d transitorios...", len(records))
    for rec in records:
        if rec.true_class is None:
            continue

        result = model.inferir(rec.alert)
        y_true.append(rec.true_class)
        y_pred.append(result.clase_predicha)

        # Brier Score multiclase: sum_c (p_c - y_c)^2
        brier = sum(
            (result.prob_transitorio[c] - (1.0 if c == rec.true_class else 0.0)) ** 2
            for c in CLASSES
        )
        brier_scores.append(brier)

        prediction_details.append(
            {
                "object_id": rec.object_id,
                "dust_severity": rec.dust_severity,
                "y_true": rec.true_class,
                "y_pred": result.clase_predicha,
                "confidence": round(result.confianza, 4),
                "entropy": round(result.entropia_shannon, 4),
                "p_dust_severa": round(result.fisica_latente["Extincion_Polvo"]["Severa"], 4),
            }
        )

    if not y_true:
        raise RuntimeError("No existen registros etiquetados con 'true_class' para evaluar.")

    cm_raw, cm_norm = compute_confusion_matrix(y_true, y_pred, CLASSES)
    clf_metrics = compute_classification_metrics(cm_raw, CLASSES)
    ea_analysis = evaluate_explaining_away(model, records, prediction_details)

    output_payload: Dict[str, Any] = {
        "n_evaluated": len(y_true),
        "classes": CLASSES,
        "global_accuracy": clf_metrics["accuracy"],
        "multiclass_brier_score": round(float(np.mean(brier_scores)), 4),
        "classification_metrics": clf_metrics,
        "confusion_matrix_raw": cm_raw.tolist(),
        "confusion_matrix_normalized": np.round(cm_norm, 4).tolist(),
        "explaining_away_analysis": ea_analysis,
    }

    metrics_file = reports_dir / "evaluation_metrics.json"
    with metrics_file.open("w", encoding="utf-8") as fh:
        json.dump(output_payload, fh, indent=4, ensure_ascii=False)

    cm_fig = figures_dir / "confusion_matrix_normalized.png"
    ea_fig = figures_dir / "explaining_away_dust_analysis.png"
    plot_confusion_matrix(cm_raw, cm_norm, CLASSES, cm_fig)
    plot_explaining_away_summary(ea_analysis, ea_fig)

    logger.info(
        "Benchmarking completado | Accuracy=%.4f | Brier=%.4f | Reporte=%s",
        output_payload["global_accuracy"],
        output_payload["multiclass_brier_score"],
        metrics_file,
    )
    return output_payload


if __name__ == "__main__":
    run_evaluation()