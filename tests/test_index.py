import os
import tempfile
import shutil

import pandas as pd
import pytest

from index import SeedIndex


@pytest.fixture
def seed_dir():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def _create_seed(path, filename, rows):
    df = pd.DataFrame(rows)
    df.to_excel(os.path.join(path, filename), index=False)


class TestSeedIndex:
    def test_index_single_file(self, seed_dir):
        _create_seed(seed_dir, "test.xlsx", [
            ("Juan", "RFC1"),
            ("Maria", "RFC2"),
        ])
        index = SeedIndex(seed_dir=seed_dir)
        files = index.get_files()
        assert len(files) == 1
        assert files[0]["filename"] == "test.xlsx"
        assert files[0]["row_count"] == 2

    def test_index_multiple_files(self, seed_dir):
        _create_seed(seed_dir, "a.xlsx", [("A", "R1")])
        _create_seed(seed_dir, "b.xlsx", [("B", "R2"), ("C", "R3")])
        index = SeedIndex(seed_dir=seed_dir)
        files = index.get_files()
        assert len(files) == 2
        assert files[0]["filename"] == "a.xlsx"
        assert files[1]["filename"] == "b.xlsx"

    def test_index_ignores_non_xlsx(self, seed_dir):
        with open(os.path.join(seed_dir, "readme.txt"), "w") as f:
            f.write("hello")
        _create_seed(seed_dir, "data.xlsx", [("A", "R1")])
        index = SeedIndex(seed_dir=seed_dir)
        assert len(index.get_files()) == 1

    def test_index_empty_dir(self, seed_dir):
        index = SeedIndex(seed_dir=seed_dir)
        assert index.get_files() == []

    def test_index_nonexistent_dir(self):
        index = SeedIndex(seed_dir="nonexistent_dir_xyz")
        assert index.get_files() == []

    def test_load_batch(self, seed_dir):
        _create_seed(seed_dir, "test.xlsx", [
            ("Juan Perez", "PEPJ850101"),
            ("Maria Lopez", "LOHM900202"),
            ("Carlos Diaz", "RADC780303"),
        ])
        index = SeedIndex(seed_dir=seed_dir)
        filepath = index.get_files()[0]["filepath"]

        batch = index.load_batch(filepath, start=0, size=2)
        assert len(batch) == 2

    def test_load_batch_with_slash_replacement(self, seed_dir):
        _create_seed(seed_dir, "test.xlsx", [("Juan/Pedro", "RFC1")])
        index = SeedIndex(seed_dir=seed_dir)
        filepath = index.get_files()[0]["filepath"]
        batch = index.load_batch(filepath, start=0, size=1)
        assert len(batch) == 1
        assert "/" not in batch[0][0]

    def test_load_batch_out_of_range(self, seed_dir):
        _create_seed(seed_dir, "test.xlsx", [("A", "R1")])
        index = SeedIndex(seed_dir=seed_dir)
        filepath = index.get_files()[0]["filepath"]
        batch = index.load_batch(filepath, start=100, size=10)
        assert batch == []

    def test_load_batch_partial(self, seed_dir):
        _create_seed(seed_dir, "test.xlsx", [
            ("A", "R1"), ("B", "R2"), ("C", "R3"),
        ])
        index = SeedIndex(seed_dir=seed_dir)
        filepath = index.get_files()[0]["filepath"]
        batch = index.load_batch(filepath, start=0, size=1)
        assert len(batch) == 1

    def test_file_info_has_basename(self, seed_dir):
        _create_seed(seed_dir, "mydata.xlsx", [("A", "R1")])
        index = SeedIndex(seed_dir=seed_dir)
        assert index.get_files()[0]["basename"] == "mydata"
