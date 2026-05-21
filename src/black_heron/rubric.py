"""Versioned rubric loader. Validates schema, falls back to bundled default."""
from __future__ import annotations

import json
from pathlib import Path

from ._models import Rubric


def load_rubric(path: Path | None = None) -> Rubric:
    """Load rubric from path or bundled default. Raises on schema/version mismatch."""
    if path is None:
        path = Path(__file__).parent / "rubric.default.json"
        source = "bundled-default"
    else:
        source = str(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    rubric = Rubric(**data)
    if rubric.schema_version != "1.0.0":
        raise ValueError(
            f"Rubric at {path} declares schema_version={rubric.schema_version!r}; "
            f"this Black Heron build only supports schema_version=1.0.0"
        )
    rubric.source = source
    return rubric
