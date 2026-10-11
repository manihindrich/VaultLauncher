import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonFileError(Exception):
    pass


def read_json(path: Path) -> Any:
    """Return parsed JSON, or None when the file does not exist.

    Raises JsonFileError when the file exists but cannot be read or parsed.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise JsonFileError(f"{path}: {e}") from e


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON so that readers never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
