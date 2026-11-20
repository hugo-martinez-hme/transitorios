"""Tests unitarios e integración para ingesta real, discretización dinámica e inferencia masiva."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.controller.real_data_loader import DataIngestionError, RealDataLoader
from src.model.dtos import (
    AstronomicalAlert,
    DiscretizationConfig,
    VALID_STATES,
    ValidationError,
)
from src.model.transient_model import TransientModel


class TestRealDataAndRobustness(unittest.TestCase):
    """Valida RealDataLoader, discretización parametrizable y estabilidad de pgmpy."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.model = TransientModel()

    def test_default_discretization_tabla_2(self) -> None:
        """Comprueba que los valores por defecto preservan exactamente la Tabla 2."""
        raw = {
            "galaxia": "Eliptica",
            "r_kpc": 0.4,
            "g_minus_r": -0.2,
            "m_v": 16.1,
            "l_x": 5e42,
            "fwhm_kms": 4500.0,
            "curva_luz": "Estocastica",
        }
        alerta = AstronomicalAlert.from_continuous(raw)
        self.assertEqual(alerta.ubicacion, "Nuclear")
        self.assertEqual(alerta.color, "Azul")
        self.assertEqual(alerta.magnitud, "Brillante")
        self.assertEqual(alerta.rayos_x, "Intensa")
        self.assertEqual(alerta.anchura_lineas, "Anchas")

    def test_dynamic_config_discretization(self) -> None:
        """Comprueba que modificar DiscretizationConfig altera los cortes sin código rígido."""
        raw = {"apparent_magnitude": 18.0, "velocity_km_s": 2500.0}
        alerta_default = AstronomicalAlert.from_continuous(raw)
        self.assertEqual(alerta_default.magnitud, "Intermedia")
        self.assertEqual(alerta_default.anchura_lineas, "Estrechas")

        custom_cfg = DiscretizationConfig(m_v=(18.5, 20.5), fwhm_kms=2000.0)
        alerta_custom = AstronomicalAlert.from_continuous(raw, config=custom_cfg)
        self.assertEqual(alerta_custom.magnitud, "Brillante")
        self.assertEqual(alerta_custom.anchura_lineas, "Anchas")

    def test_percentile_based_discretization(self) -> None:
        """Valida el cálculo dinámico de umbrales por percentiles sobre un DataFrame."""
        df = pd.DataFrame(
            {
                "apparent_magnitude": [15.0, 16.0, 18.0, 19.0, 21.0, 22.0],
                "velocity_km_s": [500.0, 1000.0, 3000.0, 6000.0, 9000.0, 12000.0],
                "dust_extinction_ebv": [0.02, 0.05, 0.20, 0.35, 0.70, 0.90],
            }
        )
        cfg = DiscretizationConfig.from_dataframe_percentiles(df, quantiles=(0.33, 0.67))
        self.assertLess(cfg.m_v[0], cfg.m_v[1])
        self.assertLess(cfg.dust_extinction_ebv[0], cfg.dust_extinction_ebv[1])

    def test_validation_errors_nan_inf_and_out_of_range(self) -> None:
        """Asegura el rechazo estricto de NaN, Inf, valores negativos y estados inválidos."""
        with self.assertRaises(ValidationError):
            AstronomicalAlert.from_continuous({"apparent_magnitude": float("nan")})

        with self.assertRaises(ValidationError):
            AstronomicalAlert.from_continuous({"velocity_km_s": float("inf")})

        with self.assertRaises(ValidationError):
            AstronomicalAlert.from_continuous({"x_ray_flux": -1e-12, "redshift_z": 0.1})

        with self.assertRaises(ValidationError):
            AstronomicalAlert.from_continuous({"galaxia": "Galaxia_Inexistente"})

    def test_real_data_loader_csv_ingestion_and_filtering(self) -> None:
        """Verifica la ingesta de CSV, validación de esquema y descarte seguro de filas corruptas."""
        csv_content = (
            "object_id,apparent_magnitude,redshift_z,velocity_km_s,x_ray_flux,dust_extinction_ebv,galaxia,true_class\n"
            "OBJ_01,16.2,0.05,9500.0,1e-16,0.04,Eliptica,SN_Ia\n"
            "OBJ_BAD,NaN,0.10,4000.0,1e-13,0.20,Espiral,AGN\n"
            "OBJ_02,18.4,0.25,5200.0,2e-12,0.65,Espiral,AGN\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "sample.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

            loader = RealDataLoader()
            records = loader.load_dataset_csv(csv_path, drop_invalid=True)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].object_id, "OBJ_01")
            self.assertEqual(records[0].dust_severity, "Baja")
            self.assertEqual(records[1].dust_severity, "Severa")
            self.assertEqual(records[1].alert.rayos_x, "Intensa")

            # Esquema incompleto debe lanzar DataIngestionError
            bad_csv = Path(tmpdir) / "bad_schema.csv"
            bad_csv.write_text("object_id,apparent_magnitude\nX,17.0\n", encoding="utf-8")
            with self.assertRaises(DataIngestionError):
                loader.load_dataset_csv(bad_csv)

    def test_batch_inference_stability_pgmpy(self) -> None:
        """Prueba de integración: inferencia exacta estable sobre un lote de 30 alertas."""
        rows = [
            f"OBJ_{i:02d},{15.5 + (i % 6)},{0.02 + 0.01 * (i % 5)},{1000.0 + 1500.0 * (i % 5)},"
            f"{1e-16 * (10 ** (i % 5))},{0.05 + 0.15 * (i % 4)},SN_Ia"
            for i in range(30)
        ]
        csv_text = (
            "object_id,apparent_magnitude,redshift_z,velocity_km_s,x_ray_flux,dust_extinction_ebv,true_class\n"
            + "\n".join(rows)
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "batch.csv"
            csv_path.write_text(csv_text, encoding="utf-8")

            records = RealDataLoader().load_dataset_csv(csv_path)
            self.assertEqual(len(records), 30)

            for rec in records:
                res = self.model.inferir(rec.alert)
                self.assertIn(res.clase_predicha, VALID_STATES["Tipo_Transitorio"])
                self.assertAlmostEqual(sum(res.prob_transitorio.values()), 1.0, places=5)
                self.assertGreaterEqual(res.entropia_shannon, 0.0)
                for dist in res.fisica_latente.values():
                    self.assertAlmostEqual(sum(dist.values()), 1.0, places=5)

    def test_allow_missing_sensors_preserves_corrupt_rejection(self) -> None:
        """Verifica evidencia parcial real en RealDataLoader sin relajar rechazo a Inf."""
        import tempfile

        csv_content = (
            "object_id,apparent_magnitude,redshift_z,velocity_km_s,x_ray_flux,"
            "dust_extinction_ebv,g_minus_r,curva_luz,true_class\n"
            "ZTF_PARTIAL_OK,18.4,0.05,,,0.12,0.05,Decaimiento_Rapido,SN_Ia\n"
            "ZTF_CORRUPT_INF,18.4,inf,,,0.12,0.05,Decaimiento_Rapido,SN_Ia\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "partial_observatory.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

            loader = RealDataLoader("config.json", use_percentiles=False)

            # En modo estricto (por defecto) ambas filas se descartan
            strict_records = loader.load_dataset_csv(csv_path, drop_invalid=True, allow_missing_sensors=False)
            self.assertEqual(len(strict_records), 0)

            # En modo observatorio real pasa la fila con sensores ausentes, pero se descarta Inf
            partial_records = loader.load_dataset_csv(csv_path, drop_invalid=True, allow_missing_sensors=True)
            self.assertEqual(len(partial_records), 1)
            self.assertEqual(partial_records[0].object_id, "ZTF_PARTIAL_OK")
            ev = partial_records[0].alert.to_evidence_dict()
            self.assertNotIn("Emision_RayosX", ev)
            self.assertNotIn("Anchura_Lineas", ev)


if __name__ == "__main__":
    unittest.main()