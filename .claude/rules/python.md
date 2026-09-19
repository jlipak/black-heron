# Python Rules — Black Heron

> Language-specific rules for `.py` files.
> Path scope: `**/*.py`.

## Style

- **Python 3.11+** target. Use modern syntax: `list[X]`, `dict[K, V]`, `X | Y` (union), `from __future__ import annotations` at top.
- **Pydantic v2** for all input/output schemas. `model_config = ConfigDict(extra="ignore")` to gracefully handle unknown fields from external sources.
- **Type hints everywhere.** Public functions must have full type signatures. Private helpers can skip if obvious.
- **No `Any`** without justification in a comment. `Any` is an admission, not a type.
- **f-strings** for formatting. `.format()` only when f-string would be ambiguous.

## Patterns

### Pydantic schemas
```python
from pydantic import BaseModel, ConfigDict, Field

class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    confidence: float = Field(ge=0.0, le=1.0)
```

### Path handling
- `from pathlib import Path` — always.
- Never use raw strings for paths in production code.
- `Path.read_text(encoding="utf-8")` not `open()`.

### JSON
- `json.dumps(..., indent=2)` for human-readable outputs.
- `json.load()` from a file path via `Path.read_text` + `json.loads` (consistent encoding).

### Subprocess
- `subprocess.check_output([...], cwd=..., stderr=subprocess.DEVNULL, text=True, timeout=10)`.
- ALWAYS catch `subprocess.CalledProcessError`, `FileNotFoundError`, `subprocess.TimeoutExpired`.
- Return sentinel value or empty list on failure. Never let an exception escape `git_log()`-style helpers.

### Anthropic SDK calls
```python
response = client.messages.create(
    model=MODEL,                                          # claude-opus-4-6 or claude-opus-4-7 only
    max_tokens=16384,                                     # generous for verifier; lens uses 4096
    system=[{
        "type": "text",
        "text": SYSTEM,
        "cache_control": {"type": "ephemeral"},           # 5-min cache, free win on multi-lens audits
    }],
    messages=[{"role": "user", "content": user}],
)
if tracker is not None:
    record_response(tracker, response, model=MODEL, lens_name=LENS_NAME)
text = "".join(getattr(b, "text", "") for b in response.content)
```

### Error handling
- Catch narrowly. `except OSError` not `except Exception`.
- Log to stderr (`print(..., file=sys.stderr)`), not to stdout (which pollutes machine-readable output).
- Return a typed sentinel where the caller can detect failure (e.g., empty list for a `list[Finding]`-returning function).

## Anti-Patterns

| Don't | Do |
|---|---|
| `except: pass` | `except OSError: <log + continue or return sentinel>` |
| `if x == None` | `if x is None` |
| `dict.get(key) or default` for falsy values | `dict[key] if key in dict else default` |
| Bare `open(path)` | `Path(path).read_text(encoding="utf-8")` |
| String concatenation for paths | `Path(parent) / "subdir" / "file.ext"` |
| `Any` in public type sig | Specific type + Pydantic schema |
| Mutable default arg `def f(x=[])` | `def f(x: list | None = None): x = x or []` |
| Magic numbers in code | Constants at module top with comment citing source |
| `import *` | Explicit imports |
| Wide-open `try` | Narrow exception types |

## Comment Discipline (Law + Anthropic internal-grade rule)

- Default: write no comments.
- Add a comment only when the WHY is non-obvious:
  - Hidden constraint ("Must come before X because Y")
  - Subtle invariant ("List is always sorted by Z")
  - Workaround for a specific bug ("hypersdk bug: see order_manager.rs::parse_trigger_workaround")
  - Behavior that would surprise a reader
- Don't explain WHAT the code does. Well-named identifiers do that.
- Don't reference the current task or commit. Those rot.

## Imports

- Order: stdlib, third-party, local (separated by blank lines).
- Within a group: alphabetical.
- `from __future__ import annotations` first.

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel

from ._models import Finding, RepoContext
```

## Tests (when we write them, v1.2)

- `tests/test_<module>.py` per source module.
- `pytest` + `pytest-asyncio` if async paths added.
- Fixtures in `tests/fixtures/` (small, hand-built sample repos).
- Mock Anthropic API responses for unit tests — do NOT spend API budget on tests.

## Cross-References

- `core.md` — workflow
- `quality.md` — testing + verification
- `docs/LAW.md` — language-agnostic laws
