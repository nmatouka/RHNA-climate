"""Load and validate config/assumptions.yaml into a typed accessor."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml

from . import paths


@lru_cache(maxsize=1)
def load_assumptions() -> dict[str, Any]:
    """Parse assumptions.yaml (cached)."""
    with open(paths.ASSUMPTIONS) as f:
        return yaml.safe_load(f)


def slugify(name: str) -> str:
    """Reproduce the climateshed slug transform EXACTLY: lowercase, then
    collapse every run of non-[a-z0-9] characters to a single hyphen.

    climateshed does NOT transliterate accents — a non-ASCII letter like 'ñ'
    is treated as a separator, so 'La Cañada Flintridge' -> 'la-ca-ada-
    flintridge'. We must match that byte-for-byte because we use the slug to
    look up climateshed records by name (fallback to the FIPS join).
    """
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
