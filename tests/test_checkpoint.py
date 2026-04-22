import os
import json
import tempfile
import shutil

import pytest

from checkpoint import Checkpoint


@pytest.fixture
def checkpoint_path():
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "state.json")
    yield path
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestCheckpoint:
    def test_mark_and_check_processed(self, checkpoint_path):
        cp = Checkpoint(path=checkpoint_path)
        assert not cp.is_processed("RFC123")
        cp.mark_processed("RFC123", {"RFC": "RFC123", "Status": "Found"})
        assert cp.is_processed("RFC123")

    def test_found_vs_not_found(self, checkpoint_path):
        cp = Checkpoint(path=checkpoint_path)
        cp.mark_processed("RFC1", {"RFC": "RFC1", "Status": "Found"})
        cp.mark_processed("RFC2", {"RFC": "RFC2", "Status": "Not found"})
        found, not_found = cp.get_results()
        assert len(found) == 1
        assert len(not_found) == 1
        assert found[0]["RFC"] == "RFC1"
        assert not_found[0]["RFC"] == "RFC2"

    def test_save_and_load(self, checkpoint_path):
        cp = Checkpoint(path=checkpoint_path)
        cp.set_current_file("test.xlsx")
        cp.mark_processed("RFC1", {"RFC": "RFC1", "Status": "Found"})
        cp.save()

        cp2 = Checkpoint(path=checkpoint_path)
        assert cp2.is_processed("RFC1")
        assert cp2._current_file == "test.xlsx"
        found, _ = cp2.get_results()
        assert len(found) == 1

    def test_save_atomic(self, checkpoint_path):
        cp = Checkpoint(path=checkpoint_path)
        cp.mark_processed("RFC1", {"RFC": "RFC1", "Status": "Found"})
        cp.save()
        assert os.path.exists(checkpoint_path)
        assert not os.path.exists(checkpoint_path + ".tmp")

    def test_load_nonexistent(self, checkpoint_path):
        cp = Checkpoint(path=checkpoint_path)
        assert not cp.is_processed("ANY")
        found, not_found = cp.get_results()
        assert found == []
        assert not_found == []

    def test_set_current_file(self, checkpoint_path):
        cp = Checkpoint(path=checkpoint_path)
        cp.set_current_file("myfile.xlsx")
        assert cp._current_file == "myfile.xlsx"

    def test_multiple_processed(self, checkpoint_path):
        cp = Checkpoint(path=checkpoint_path)
        for i in range(10):
            cp.mark_processed(f"RFC{i}", {"RFC": f"RFC{i}", "Status": "Found"})
        assert cp._processed == {f"RFC{i}" for i in range(10)}
