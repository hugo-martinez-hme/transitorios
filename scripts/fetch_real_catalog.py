"""Pipeline ETL reproducible para congelar un catálogo multi-observatorio real.

Fuentes astronómicas abiertas integradas:
- ZTF Bright Transient Survey (Caltech): SN Ia y SN II confirmadas espectroscópicamente.
- ALeRCE Broker (ZTF): fotometría multibanda (g, r) y estrellas variables (RRL, LPV).
- ESA XMM-Newton Science Archive (XSA, TAP): flujos reales en rayos X (0.2-12 keV).
- SDSS DR18 SkyServer (SQL): espectros QSO/AGN con redshift z y fotometría óptica.
- NASA/IPAC IRSA Galactic Dust: extinción galáctica E(B-V) (Schlafly & Finkbeiner 2011).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

from alerce.core import Alerce
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.ipac.irsa.irsa_dust import IrsaDust
import numpy as np
import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("RAIN.RealCatalogETL")

ZTF_BTS_URL = "https://sites.astro.caltech.edu/ztf/bts/explorer.php?format=csv"
ESA_XSA_TAP_URL = "https://nxsa.esac.esa.int/tap-server/tap/sync"
SDSS_SQL_URL = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

CANONICAL_COLUMNS = [
    "object_id",
    "apparent_magnitude",
    "redshift_z",
    "velocity_km_s",
    "x_ray_flux",
    "dust_extinction_ebv",
    "galaxia",
    "r_kpc",
    "g_minus_r",
    "curva_luz",
    "true_class",
    "ra_deg",
    "dec_deg",
    "source_catalog",
]


def _parse_numeric_or_none(val: Any) -> Optional[float]:
    """Convierte a float solo mediciones exactas (descarta límites '>' y '-')."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s == "-" or s.startswith(">") or s.startswith("<"):
        return None
    try:
        num = float(s)
        return num if np.isfinite(num) else None
    except ValueError:
        return None


def _get_alerce_magstats_color_and_mag(
    client: Alerce, oid: str, use_peak: bool = True
) -> tuple[Optional[float], Optional[float]]:
    """Obtiene (apparent_magnitude, g_minus_r) desde ALeRCE magstats (fid 1=g, 2=r)."""
    try:
        ms = client.query_magstats(oid, format="pandas")
    except Exception:
        return None, None
    if ms is None or ms.empty or "fid" not in ms.columns:
        return None, None

    col = "magmin" if use_peak else "magmean"
    g_rows = ms[ms["fid"] == 1][col].dropna()
    r_rows = ms[ms["fid"] == 2][col].dropna()

    mag_g = float(g_rows.iloc[0]) if not g_rows.empty else None
    mag_r = float(r_rows.iloc[0]) if not r_rows.empty else None

    apparent_mag = mag_r if mag_r is not None else mag_g
    g_minus_r = (mag_g - mag_r) if (mag_g is not None and mag_r is not None) else None
    return apparent_mag, g_minus_r


def fetch_ztf_bts_supernovae(
    client: Alerce,
    per_class: int = 50,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Descarga SN Ia y SN II confirmadas espectroscópicamente de ZTF BTS + color de ALeRCE."""
    logger.info("Descargando catálogo ZTF Bright Transient Survey (Caltech)...")
    resp = requests.get(ZTF_BTS_URL, timeout=30)
    resp.raise_for_status()
    bts = pd.read_csv(io.StringIO(resp.text.lstrip()))

    bts["peakmag_num"] = pd.to_numeric(bts["peakmag"], errors="coerce")
    bts["z_num"] = pd.to_numeric(bts["redshift"], errors="coerce")
    bts["av_num"] = pd.to_numeric(bts["A_V"], errors="coerce")
    bts["ebv_num"] = bts["av_num"] / 3.1

    valid = bts.dropna(subset=["ZTFID", "RA", "Dec", "peakmag_num", "z_num", "ebv_num"])
    valid = valid[(valid["z_num"] > 0.001) & (valid["ebv_num"] >= 0.0)]

    rng = np.random.default_rng(seed)
    records: List[Dict[str, Any]] = []

    for bts_type, rain_class in [("SN Ia", "SN_Ia"), ("SN II", "SN_II")]:
        subset = valid[valid["type"] == bts_type].copy()

        # Muestreo estratificado por severidad de polvo para evaluar explaining away real
        tier_low = subset[subset["ebv_num"] < 0.15]
        tier_mid = subset[(subset["ebv_num"] >= 0.15) & (subset["ebv_num"] < 0.50)]
        tier_high = subset[subset["ebv_num"] >= 0.50]

        target_per_tier = max(1, per_class // 3)
        chosen_frames: List[pd.DataFrame] = []
        used_ids: set[str] = set()

        for tier_df in (tier_high, tier_mid, tier_low):
            take = min(len(tier_df), target_per_tier)
            if take > 0:
                idx = rng.choice(tier_df.index.to_numpy(), size=take, replace=False)
                picked = tier_df.loc[idx]
                chosen_frames.append(picked)
                used_ids.update(picked["ZTFID"].astype(str).tolist())

        # Completar hasta per_class si algún estrato tiene pocos objetos reales
        selected = pd.concat(chosen_frames, ignore_index=True) if chosen_frames else pd.DataFrame()
        remaining_needed = per_class - len(selected)
        if remaining_needed > 0:
            pool = subset[~subset["ZTFID"].astype(str).isin(used_ids)]
            extra_n = min(len(pool), remaining_needed)
            if extra_n > 0:
                idx = rng.choice(pool.index.to_numpy(), size=extra_n, replace=False)
                selected = pd.concat([selected, pool.loc[idx]], ignore_index=True)

        logger.info(
            "Procesando %d objetos %s reales (consultando color g-r en ALeRCE)...",
            len(selected),
            rain_class,
        )
        for _, row in selected.iterrows():
            ztfid = str(row["ZTFID"]).strip()
            coord = SkyCoord(str(row["RA"]), str(row["Dec"]), unit=(u.hourangle, u.deg), frame="icrs")

            _, g_minus_r = _get_alerce_magstats_color_and_mag(client, ztfid, use_peak=True)

            # Regla puramente física y agnóstica de clase basada en tiempo de decaimiento medido
            fade_days = _parse_numeric_or_none(row.get("fade"))
            if fade_days is not None:
                curva_luz = "Decaimiento_Rapido" if fade_days <= 25.0 else "Meseta"
            else:
                curva_luz = ""

            records.append(
                {
                    "object_id": ztfid,
                    "apparent_magnitude": round(float(row["peakmag_num"]), 4),
                    "redshift_z": round(float(row["z_num"]), 6),
                    "velocity_km_s": np.nan,
                    "x_ray_flux": np.nan,
                    "dust_extinction_ebv": round(float(row["ebv_num"]), 5),
                    "galaxia": "",
                    "r_kpc": np.nan,
                    "g_minus_r": round(g_minus_r, 4) if g_minus_r is not None else np.nan,
                    "curva_luz": curva_luz,
                    "true_class": rain_class,
                    "ra_deg": round(float(coord.ra.deg), 6),
                    "dec_deg": round(float(coord.dec.deg), 6),
                    "source_catalog": "ZTF_BTS+ALeRCE",
                }
            )

    return records


def fetch_xmm_sdss_agns(per_class: int = 50, seed: int = 42) -> List[Dict[str, Any]]:
    """Cruza fuentes XMM-Newton (ESA) con espectros QSO/AGN de SDSS DR18 a radio <= 5 arcsec."""
    logger.info("Consultando fuentes de rayos X en ESA XMM-Newton (XSA TAP)...")
    adql = (
        "SELECT TOP 800 ra, dec, ep_flux "
        "FROM xsa.v_epic_source_cat "
        "WHERE classopt_prob_agn >= 0.75 "
        "AND ep_flux > 1e-15 "
        "AND ra BETWEEN 130.0 AND 240.0 "
        "AND dec BETWEEN 0.0 AND 55.0"
    )
    resp = requests.get(
        ESA_XSA_TAP_URL,
        params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql},
        timeout=30,
    )
    resp.raise_for_status()
    xmm_df = pd.read_csv(io.StringIO(resp.text)).dropna(subset=["ra", "dec", "ep_flux"])
    xmm_df = xmm_df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    logger.info("ESA XMM-Newton devolvió %d candidatas de rayos X en la huella SDSS.", len(xmm_df))

    records: List[Dict[str, Any]] = []
    seen_spec_ids: set[str] = set()
    batch_size = 20
    box_deg = 0.002  # ~7.2 arcsec

    for start in range(0, len(xmm_df), batch_size):
        if len(records) >= per_class:
            break
        batch = xmm_df.iloc[start : start + batch_size]
        clauses = [
            f"(p.ra BETWEEN {r.ra - box_deg:.6f} AND {r.ra + box_deg:.6f} "
            f"AND p.dec BETWEEN {r.dec - box_deg:.6f} AND {r.dec + box_deg:.6f})"
            for r in batch.itertuples(index=False)
        ]
        sql = (
            "SELECT s.specObjID, p.ra, p.dec, p.psfMag_g, p.psfMag_r, p.extinction_r, s.z, s.class "
            "FROM PhotoObj p "
            "JOIN SpecObj s ON s.bestobjid = p.objid "
            "WHERE s.class = 'QSO' AND s.z BETWEEN 0.01 AND 1.5 "
            "AND p.psfMag_r BETWEEN 13.0 AND 22.5 AND p.psfMag_g BETWEEN 13.0 AND 23.5 "
            f"AND ({' OR '.join(clauses)})"
        )
        try:
            r_sdss = requests.get(
                SDSS_SQL_URL,
                params={"cmd": sql, "format": "csv"},
                timeout=25,
            )
            r_sdss.raise_for_status()
        except Exception as exc:
            logger.warning("Lote SDSS %d omitido por error de red: %s", start, exc)
            continue

        clean_lines = [ln for ln in r_sdss.text.splitlines() if ln.strip() and not ln.startswith("#")]
        if len(clean_lines) <= 1:
            continue

        sdss_df = pd.read_csv(io.StringIO("\n".join(clean_lines)))
        if sdss_df.empty:
            continue

        xmm_coords = SkyCoord(ra=batch["ra"].to_numpy() * u.deg, dec=batch["dec"].to_numpy() * u.deg)
        sdss_coords = SkyCoord(ra=sdss_df["ra"].to_numpy() * u.deg, dec=sdss_df["dec"].to_numpy() * u.deg)
        idx_xmm, sep2d, _ = sdss_coords.match_to_catalog_sky(xmm_coords)

        for i, (m_idx, sep) in enumerate(zip(idx_xmm, sep2d)):
            if len(records) >= per_class:
                break
            if sep.arcsec > 5.0:
                continue

            srow = sdss_df.iloc[i]
            spec_id = f"SDSS_{int(srow['specObjID'])}"
            if spec_id in seen_spec_ids:
                continue
            seen_spec_ids.add(spec_id)

            xrow = batch.iloc[int(m_idx)]
            ebv = max(0.0, float(srow["extinction_r"]) / 2.751)

            records.append(
                {
                    "object_id": spec_id,
                    "apparent_magnitude": round(float(srow["psfMag_r"]), 4),
                    "redshift_z": round(float(srow["z"]), 6),
                    "velocity_km_s": np.nan,
                    "x_ray_flux": float(xrow["ep_flux"]),
                    "dust_extinction_ebv": round(ebv, 5),
                    "galaxia": "",
                    "r_kpc": np.nan,
                    "g_minus_r": round(float(srow["psfMag_g"] - srow["psfMag_r"]), 4),
                    "curva_luz": "",
                    "true_class": "AGN",
                    "ra_deg": round(float(srow["ra"]), 6),
                    "dec_deg": round(float(srow["dec"]), 6),
                    "source_catalog": "ESA_XMM+SDSS_DR18",
                }
            )

    logger.info("Cruce ESA XMM-Newton x SDSS DR18 completado: %d AGNs confirmados.", len(records))
    return records


def fetch_alerce_variable_stars(
    client: Alerce,
    per_class: int = 50,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Descarga estrellas variables reales (RRL y LPV) de ALeRCE (ZTF) + polvo IRSA."""
    logger.info("Consultando estrellas variables reales (RRL y LPV) en ALeRCE...")
    frames: List[pd.DataFrame] = []
    for subcls in ("RRL", "LPV"):
        df = client.query_objects(
            classifier="lc_classifier",
            class_name=subcls,
            probability=0.6,
            page_size=max(40, per_class),
            format="pandas",
        )
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        return []

    pool = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["oid"])
    pool = pool.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    records: List[Dict[str, Any]] = []
    for _, row in pool.iterrows():
        if len(records) >= per_class:
            break
        oid = str(row["oid"])
        ra = float(row["meanra"])
        dec = float(row["meandec"])

        apparent_mag, g_minus_r = _get_alerce_magstats_color_and_mag(client, oid, use_peak=False)
        if apparent_mag is None or g_minus_r is None:
            continue

        # Extinción galáctica real en la línea de visión vía NASA/IPAC IRSA Dust
        try:
            coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
            dust_tbl = IrsaDust.get_query_table(coord, section="ebv")
            ebv = max(0.0, float(dust_tbl["ext SandF mean"][0]))
        except Exception as exc:
            logger.warning("IRSA Dust falló para %s (%s); se omite.", oid, exc)
            continue

        # Persistencia observacional objetiva (línea base de detecciones > 200 días)
        deltajd = _parse_numeric_or_none(row.get("deltajd"))
        curva_luz = "Estocastica" if (deltajd is not None and deltajd >= 200.0) else ""

        records.append(
            {
                "object_id": oid,
                "apparent_magnitude": round(apparent_mag, 4),
                "redshift_z": np.nan,
                "velocity_km_s": np.nan,
                "x_ray_flux": np.nan,
                "dust_extinction_ebv": round(ebv, 5),
                "galaxia": "",
                "r_kpc": np.nan,
                "g_minus_r": round(g_minus_r, 4),
                "curva_luz": curva_luz,
                "true_class": "Variable_Estelar",
                "ra_deg": round(ra, 6),
                "dec_deg": round(dec, 6),
                "source_catalog": "ALeRCE_ZTF+IRSA_Dust",
            }
        )
        time.sleep(0.05)

    logger.info("Estrellas variables reales recopiladas: %d.", len(records))
    return records


def build_real_catalog(
    output_csv: Path = Path("data/real_ztf_catalog.csv"),
    output_meta: Path = Path("data/real_ztf_catalog_metadata.json"),
    per_class: int = 50,
    seed: int = 42,
) -> None:
    """Ejecuta el ETL completo y congela el catálogo real y sus metadatos de procedencia."""
    client = Alerce()
    all_records: List[Dict[str, Any]] = []
    all_records.extend(fetch_ztf_bts_supernovae(client, per_class=per_class, seed=seed))
    all_records.extend(fetch_xmm_sdss_agns(per_class=per_class, seed=seed))
    all_records.extend(fetch_alerce_variable_stars(client, per_class=per_class, seed=seed))

    df = pd.DataFrame(all_records, columns=CANONICAL_COLUMNS)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)

    completeness = {
        col: round(float(df[col].replace("", np.nan).notna().mean()), 4)
        for col in [
            "apparent_magnitude",
            "g_minus_r",
            "redshift_z",
            "x_ray_flux",
            "velocity_km_s",
            "dust_extinction_ebv",
            "curva_luz",
        ]
    }
    dust_counts = {
        "Baja (<0.15)": int((df["dust_extinction_ebv"] < 0.15).sum()),
        "Moderada (0.15-0.50)": int(((df["dust_extinction_ebv"] >= 0.15) & (df["dust_extinction_ebv"] < 0.50)).sum()),
        "Severa (>=0.50)": int((df["dust_extinction_ebv"] >= 0.50).sum()),
    }
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "total_objects": int(len(df)),
        "counts_by_class": {k: int(v) for k, v in df["true_class"].value_counts().items()},
        "counts_by_source": {k: int(v) for k, v in df["source_catalog"].value_counts().items()},
        "dust_ebv_distribution": dust_counts,
        "sensor_completeness_ratio": completeness,
        "sources": [
            "ZTF Bright Transient Survey (Caltech) - https://sites.astro.caltech.edu/ztf/bts/",
            "ALeRCE Broker (ZTF) - https://alerce.science/",
            "ESA XMM-Newton Science Archive (4XMM EPIC TAP) - https://nxsa.esac.esa.int/",
            "SDSS DR18 SkyServer - https://skyserver.sdss.org/dr18/",
            "NASA/IPAC IRSA Galactic Dust Reddening and Extinction (Schlafly & Finkbeiner 2011)",
        ],
    }
    output_meta.write_text(json.dumps(metadata, indent=4, ensure_ascii=False), encoding="utf-8")
    logger.info("Catálogo real congelado en '%s' (%d objetos).", output_csv, len(df))
    logger.info("Metadatos guardados en '%s'.", output_meta)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarga y congela un catálogo astrofísico real.")
    parser.add_argument("--per-class", type=int, default=50, help="Número objetivo de objetos por clase.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla de reproducibilidad.")
    args = parser.parse_args()
    build_real_catalog(per_class=args.per_class, seed=args.seed)
