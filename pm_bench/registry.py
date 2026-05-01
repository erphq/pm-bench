"""Dataset registry - typed view of registry.yml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).parent / "registry.yml"


@dataclass(frozen=True)
class Dataset:
    name: str
    title: str
    cases: int
    events: int
    license: str
    format: str
    landing_url: str | None = None
    download_url: str | None = None
    sha256: str | None = None
    bundled: bool = False


def load_registry(path: Path | None = None) -> list[Dataset]:
    """Load and return every dataset declared in `registry.yml`."""
    p = path or REGISTRY_PATH
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    items = raw.get("datasets") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"{p}: expected top-level 'datasets:' list")
    out: list[Dataset] = []
    for d in items:
        out.append(Dataset(**d))
    return out


def get_dataset(name: str) -> Dataset:
    """Look up a dataset by `name`. Raises `KeyError` if unknown."""
    for d in load_registry():
        if d.name == name:
            return d
    raise KeyError(name)
