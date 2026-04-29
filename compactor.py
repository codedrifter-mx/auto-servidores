import os

import pandas as pd


class Compactor:
    def __init__(self, output_dir, found_suffix, not_found_suffix, years):
        self.output_dir = output_dir
        self.found_suffix = found_suffix
        self.not_found_suffix = not_found_suffix
        self.years = years

    def compact(self, found, not_found, base_filename):
        os.makedirs(self.output_dir, exist_ok=True)
        year_cols = [f"noComprobante_{y}" for y in self.years]
        base_cols = ["Name", "RFC"] + year_cols

        found_filtered = [
            {col: r.get(col, "") for col in base_cols}
            for r in found
        ]
        not_found_filtered = [
            {"Name": r["Name"], "RFC": r["RFC"]}
            for r in not_found
        ]

        found_path = os.path.join(self.output_dir, f"{base_filename}{self.found_suffix}.xlsx")
        not_found_path = os.path.join(self.output_dir, f"{base_filename}{self.not_found_suffix}.xlsx")

        if found_filtered:
            pd.DataFrame(found_filtered).to_excel(found_path, index=False)
        if not_found_filtered:
            pd.DataFrame(not_found_filtered).to_excel(not_found_path, index=False)

        return {
            "found_count": len(found_filtered),
            "not_found_count": len(not_found_filtered),
            "found_path": found_path if found_filtered else None,
            "not_found_path": not_found_path if not_found_filtered else None,
        }
