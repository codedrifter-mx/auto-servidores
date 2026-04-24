import os

import pandas as pd


class SeedIndex:
    def __init__(self, seed_dir="seed"):
        self.seed_dir = seed_dir
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
