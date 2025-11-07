import re
import tomllib
from pathlib import Path

def read_line_length_config(root: str) -> int:
    """Detect max line length from flake8/black configs or use default."""
    root = Path(root)
    default_length = 79

    toml_path = root / "pyproject.toml"
    if toml_path.exists():
        try:
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            if "tool" in data:
                black_cfg = data["tool"].get("black", {})
                flake_cfg = data["tool"].get("flake8", {})
                return black_cfg.get("line-length") or flake_cfg.get("max-line-length") or default_length
        except Exception:
            pass

    for cfg_name in ("setup.cfg", "tox.ini"):
        cfg = root / cfg_name
        if cfg.exists():
            for line in cfg.read_text().splitlines():
                m = re.match(r"max-line-length\s*=\s*(\d+)", line)
                if m:
                    return int(m.group(1))

    return default_length


def check_line_length(file_path: str, max_length: int) -> list[tuple[int, str]]:
    """Return list of (lineno, message) for long lines."""
    warnings = []

    with open(file_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if len(line.rstrip("\n")) > max_length:
                warnings.append((i, f"E501: line too long ({len(line)} > {max_length})"))

    return warnings

