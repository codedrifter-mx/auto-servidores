import os
import tempfile
import shutil

import pandas as pd
import pytest

from compactor import Compactor


@pytest.fixture
def output_dir():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestCompactor:
    def test_compact_found_and_not_found(self, output_dir):
        compactor = Compactor(output_dir, "_FOUND", "_NOT_FOUND", [2025, 2026])
        found = [
            {"Name": "A", "RFC": "RFC1", "Status": "Found", "noComprobante_2025": "X1", "noComprobante_2026": "X2"},
        ]
        not_found = [
            {"Name": "B", "RFC": "RFC2", "Status": "Not found"},
        ]
        summary = compactor.compact(found, not_found, "test")

        assert summary["found_count"] == 1
        assert summary["not_found_count"] == 1
        assert os.path.exists(summary["found_path"])
        assert os.path.exists(summary["not_found_path"])

        df_found = pd.read_excel(summary["found_path"])
        assert "Name" in df_found.columns
        assert "RFC" in df_found.columns
        assert "noComprobante_2025" in df_found.columns

    def test_compact_empty_lists(self, output_dir):
        compactor = Compactor(output_dir, "_FOUND", "_NOT_FOUND", [2025])
        summary = compactor.compact([], [], "test")
        assert summary["found_count"] == 0
        assert summary["not_found_count"] == 0
        assert summary["found_path"] is None
        assert summary["not_found_path"] is None

    def test_compact_only_found(self, output_dir):
        compactor = Compactor(output_dir, "_FOUND", "_NOT_FOUND", [2025])
        found = [{"Name": "A", "RFC": "RFC1", "Status": "Found", "noComprobante_2025": "X"}]
        summary = compactor.compact(found, [], "test")
        assert summary["found_count"] == 1
        assert summary["not_found_count"] == 0
        assert summary["not_found_path"] is None
        assert os.path.exists(summary["found_path"])

    def test_compact_only_not_found(self, output_dir):
        compactor = Compactor(output_dir, "_FOUND", "_NOT_FOUND", [2025])
        not_found = [{"Name": "B", "RFC": "RFC2", "Status": "Not found"}]
        summary = compactor.compact([], not_found, "test")
        assert summary["found_count"] == 0
        assert summary["not_found_count"] == 1
        assert summary["found_path"] is None
        assert os.path.exists(summary["not_found_path"])

    def test_output_filenames(self, output_dir):
        compactor = Compactor(output_dir, "_ENCONTRADOS", "_NO_ENCONTRADOS", [2025])
        found = [{"Name": "A", "RFC": "RFC1", "Status": "Found", "noComprobante_2025": "X"}]
        not_found = [{"Name": "B", "RFC": "RFC2", "Status": "Not found"}]
        summary = compactor.compact(found, not_found, "myfile")

        assert "myfile_ENCONTRADOS.xlsx" in summary["found_path"]
        assert "myfile_NO_ENCONTRADOS.xlsx" in summary["not_found_path"]

    def test_year_columns_in_output(self, output_dir):
        compactor = Compactor(output_dir, "_FOUND", "_NOT_FOUND", [2024, 2025, 2026])
        found = [{"Name": "A", "RFC": "RFC1", "Status": "Found",
                  "noComprobante_2024": "A", "noComprobante_2025": "B", "noComprobante_2026": "C"}]
        summary = compactor.compact(found, [], "test")
        df = pd.read_excel(summary["found_path"])
        assert "noComprobante_2024" in df.columns
        assert "noComprobante_2025" in df.columns
        assert "noComprobante_2026" in df.columns
