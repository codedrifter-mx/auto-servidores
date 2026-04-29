import os
import shutil
import sys

import pandas as pd


def _app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_APP_DIR = _app_dir()


class SeedIndex:
    def __init__(self, seed_dir=None):
        _is_default = seed_dir is None
        if _is_default:
            seed_dir = os.path.join(_APP_DIR, "seed")
        self.seed_dir = seed_dir
        if _is_default:
            os.makedirs(self.seed_dir, exist_ok=True)
            if not os.listdir(self.seed_dir):
                bundled = getattr(sys, '_MEIPASS', _APP_DIR)
                bundled_seed = os.path.join(bundled, "seed")
                if os.path.exists(bundled_seed) and bundled_seed != self.seed_dir:
                    try:
                        for item in os.listdir(bundled_seed):
                            s = os.path.join(bundled_seed, item)
                            d = os.path.join(self.seed_dir, item)
                            if not os.path.exists(d):
                                shutil.copy2(s, d)
                    except Exception:
                        pass
        self.index = []
        self._df_cache = {}
        self._build_index()

    def _build_index(self):
        if not os.path.exists(self.seed_dir):
            return
        for filename in sorted(os.listdir(self.seed_dir)):
            if filename.endswith(".xlsx"):
                filepath = os.path.join(self.seed_dir, filename)
                df = pd.read_excel(filepath)
                self.index.append({
                    "filename": filename,
                    "filepath": filepath,
                    "basename": os.path.splitext(filename)[0],
                    "row_count": len(df),
                })

    def get_files(self):
        return self.index

    def load_batch(self, filepath, start=0, size=50):
        if filepath not in self._df_cache:
            self._df_cache[filepath] = pd.read_excel(filepath)
        df = self._df_cache[filepath]
        batch = df.iloc[start:start + size]
        return [
            (row.iloc[0].upper().strip().replace("/", " "), row.iloc[1])
            for _, row in batch.iterrows()
        ]
