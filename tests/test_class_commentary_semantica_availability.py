import importlib.metadata
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from class_commentary_semantica import (
    SemanticaGraphAdapter,
    SemanticaGraphUnavailableError,
)


class SemanticaAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "graph.json"
        self.store_path.write_text(
            '{"format_version": "xingrun.class_commentary.semantica.v1", "nodes": [], "edges": []}',
            encoding="utf-8",
        )
        self.adapter = SemanticaGraphAdapter(self.store_path)

    def test_health_degrades_when_semantica_is_missing(self):
        with patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError("semantica"),
        ):
            self.assertEqual(
                self.adapter.health(),
                {"healthy": False, "error": "semantica_unavailable"},
            )

    def test_readiness_degrades_when_semantica_is_missing(self):
        with patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError("semantica"),
        ):
            self.assertEqual(
                self.adapter.readiness(),
                {"healthy": False, "error": "semantica_unavailable"},
            )

    def test_patch_releases_of_the_required_series_are_accepted(self):
        for version in ("0.6.0", "0.6.1", "0.6.15"):
            with self.subTest(version=version):
                with patch.object(importlib.metadata, "version", return_value=version):
                    self.assertEqual(self.adapter._installed_version(), version)

    def test_other_major_or_minor_versions_are_rejected(self):
        for bad in ("0.5.9", "0.7.0", "1.0.0"):
            with self.subTest(version=bad):
                with patch.object(importlib.metadata, "version", return_value=bad):
                    with self.assertRaises(SemanticaGraphUnavailableError):
                        self.adapter._installed_version()


if __name__ == "__main__":
    unittest.main()
