"""Módulo de ingesta y validación de datasets tabulares de transitorios astrofísicos."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.model.dtos import (
    AstronomicalAlert,
    DiscretizationConfig,
    VALID_STATES,
    ValidationError,
    discretize_dust_ebv,
)

logger = logging.getLogger("RAIN.RealDataLoader")


class DataIngestionError(Exception):
    """Excepción para errores de acceso, esquema o formato en datasets CSV."""


@dataclass(frozen=True)
class TransientRecord:
    """Registro validado listo para inferencia por lotes y evaluación de métricas."""

    object_id: str
    alert: AstronomicalAlert
    dust_extinction_ebv: float
    dust_severity: str
    redshift_z: float
    true_class: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class RealDataLoader:
    """Cargador robusto de alertas astrofísicas desde CSV con discretización dinámica."""

    REQUIRED_COLUMNS: Tuple[str, ...] = (
        "object_id",
        "apparent_magnitude",
        "redshift_z",
        "velocity_km_s",
        "x_ray_flux",
        "dust_extinction_ebv",
    )

    REQUIRED_NUMERIC_COLUMNS: Tuple[str, ...] = (
        "apparent_magnitude",
        "redshift_z",
        "velocity_km_s",
        "x_ray_flux",
        "dust_extinction_ebv",
    )

    OPTIONAL_COLUMNS: Tuple[str, ...] = (
        "galaxia",
        "ubicacion",
        "r_kpc",
        "color",
        "g_minus_r",
        "curva_luz",
        "true_class",
    )

    def __init__(
        self,
        config_path: Union[str, Path] = "config.json",
        use_percentiles: Optional[bool] = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.raw_config = self._load_raw_json()
        self.base_config = DiscretizationConfig.from_json(self.config_path)
        if use_percentiles is None:
            self.use_percentiles = self.raw_config.get("discretization_mode") == "percentiles"
        else:
            self.use_percentiles = use_percentiles
        q = self.raw_config.get("percentile_quantiles", [0.33, 0.67])
        self.percentile_quantiles: Tuple[float, float] = (float(q[0]), float(q[1]))

    def _load_raw_json(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            with self.config_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            raise DataIngestionError(f"Error al parsear '{self.config_path}': {exc}") from exc

    @staticmethod
    def _clean_optional(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
        if pd.isna(value):
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def load_dataset_csv(
        self,
        file_path: Union[str, Path],
        drop_invalid: bool = True,
    ) -> List[TransientRecord]:
        """Ingiere, valida y discretiza un dataset CSV de eventos transitorios.

        Parameters
        ----------
        file_path : str | Path
            Ruta al fichero CSV.
        drop_invalid : bool, default=True
            Si es True descarta filas corruptas registrando un warning; si es False
            relanza `ValidationError` ante la primera anomalía.

        Returns
        -------
        List[TransientRecord]
            Lista de registros validados con su DTO `AstronomicalAlert` acoplado.
        """
        path = Path(file_path)
        if not path.exists():
            raise DataIngestionError(f"El fichero CSV no existe: {path}")

        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise DataIngestionError(f"Error leyendo CSV '{path}': {exc}") from exc

        missing_cols = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise DataIngestionError(f"Esquema CSV inválido. Faltan columnas obligatorias: {missing_cols}")

        active_config = (
            DiscretizationConfig.from_dataframe_percentiles(
                df, quantiles=self.percentile_quantiles, base_config=self.base_config
            )
            if self.use_percentiles
            else self.base_config
        )

        records: List[TransientRecord] = []
        discarded = 0

        for idx, row in df.iterrows():
            try:
                obj_id_raw = self._clean_optional(row["object_id"])
                if obj_id_raw is None:
                    raise ValidationError("El campo obligatorio 'object_id' está vacío o nulo.")

                # Verificación estricta de columnas numéricas obligatorias
                payload: Dict[str, Any] = {}
                for col in self.REQUIRED_NUMERIC_COLUMNS:
                    val = row[col]
                    if pd.isna(val):
                        raise ValidationError(f"Valor nulo en columna obligatoria '{col}'.")
                    payload[col] = val

                # Campos opcionales observables (pueden ser None para evidencia parcial)
                for opt_col in self.OPTIONAL_COLUMNS:
                    if opt_col in df.columns and opt_col != "true_class":
                        cleaned = self._clean_optional(row[opt_col])
                        if cleaned is not None:
                            payload[opt_col] = cleaned

                dust_ebv = float(payload["dust_extinction_ebv"])
                redshift_z = float(payload["redshift_z"])
                dust_severity = discretize_dust_ebv(dust_ebv, config=active_config)

                # Si no hay color directo pero sí extinción severa/baja, NO inventamos color:
                # preservamos la evidencia parcial real del telescopio.
                alert = AstronomicalAlert.from_continuous(payload, config=active_config)

                true_class: Optional[str] = None
                if "true_class" in df.columns:
                    raw_label = self._clean_optional(row["true_class"])
                    if raw_label is not None:
                        label_str = str(raw_label).strip()
                        if label_str not in VALID_STATES["Tipo_Transitorio"]:
                            raise ValidationError(
                                f"Etiqueta real '{label_str}' inválida. "
                                f"Permitidas: {VALID_STATES['Tipo_Transitorio']}"
                            )
                        true_class = label_str

                records.append(
                    TransientRecord(
                        object_id=str(obj_id_raw).strip(),
                        alert=alert,
                        dust_extinction_ebv=dust_ebv,
                        dust_severity=dust_severity,
                        redshift_z=redshift_z,
                        true_class=true_class,
                        raw_data=payload,
                    )
                )
            except ValidationError as ve:
                discarded += 1
                logger.warning("Fila %s descartada por validación física: %s", idx, ve)
                if not drop_invalid:
                    raise

        logger.info(
            "Ingesta de '%s' completada: %d válidos, %d descartados (total=%d).",
            path.name,
            len(records),
            discarded,
            len(df),
        )
        return records