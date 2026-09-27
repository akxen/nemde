"""Library module: local casefile storage backend used by run.py, service.py."""

import json
from pathlib import Path
from typing import Any, Protocol

from nemde.casefile_io import normalize_casefile


class FileService(Protocol):
    def save_artefact(self, data, relative_path: Path) -> bool: ...
    def load_artefact(self, relative_path: Path) -> Any: ...


class LocalFileService:
    def __init__(self, params: dict) -> None:
        self.data_dir = params["output_dir"]

    def save_artefact(self, data: Any, relative_path: Path) -> bool:
        path = Path(self.data_dir, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.suffix == ".csv":
            data.to_csv(path, index=False)
        elif path.suffix == ".html":
            path.write_text(data, encoding="utf-8")
        elif path.suffix == ".json":
            path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            raise Exception(f"Unable to save file: {relative_path}")

        return True

    def load_artefact(self, relative_path: Path) -> Any:
        path = Path(self.data_dir, relative_path)

        if path.suffix != ".loaded":
            raise Exception(f"Unable to load file: {relative_path}")

        with open(path) as f:
            data = f.read()
        return normalize_casefile(data)
