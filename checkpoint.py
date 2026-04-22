import json
import os


class Checkpoint:
    def __init__(self, path=".checkpoint/state.json"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._processed = set()
        self._found = []
        self._not_found = []
        self._current_file = None
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                state = json.load(f)
            self._processed = set(state.get("processed_rfc", []))
            self._found = state.get("found", [])
            self._not_found = state.get("not_found", [])
            self._current_file = state.get("current_file")

    def save(self):
        state = {
            "processed_rfc": list(self._processed),
            "found": self._found,
            "not_found": self._not_found,
            "current_file": self._current_file,
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, self.path)

    def is_processed(self, rfc):
        return rfc in self._processed

    def mark_processed(self, rfc, result):
        self._processed.add(rfc)
        if result.get("Status") == "Found":
            self._found.append(result)
        else:
            self._not_found.append(result)

    def get_results(self):
        return self._found, self._not_found

    def set_current_file(self, filename):
        self._current_file = filename
