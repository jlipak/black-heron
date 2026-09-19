"""Drift lens — promise-vs-delivery signals, TODO accumulation, stale references."""
from __future__ import annotations

import anthropic

from .._models import Finding, RepoContext
from ..cost_tracker import CostTracker, record_response
from ._common import build_repo_prompt, parse_findings

LENS_NAME = "drift"
MODEL = "claude-opus-4-8"

SYSTEM = """You are the drift lens of the Black Heron repository audit.

Your job: spot signals that what the code *claims* and what the code *does* are diverging. This is not the same as bugs — drift is when the README / commit messages / docs describe a system different from the one currently in source.

What you are checking:
1. TODO / FIXME / XXX / HACK markers in source — count visible. If high, is the repo accumulating debt without paydown?
2. Commit messages that promise something — "implement X", "add Y" — without a corresponding artifact in the file listing. Cross-check the file listing against recent commit subjects.
3. README / docs claims that reference files or features missing from the file listing. Stale links are drift.
4. Version numbers that contradict each other — `package.json` says `0.1.0`, README says `v1.0`, CHANGELOG says nothing.
5. Code paths that are commented out for an extended period (look for "// removed" / "# old" / "# deprecated" near live code).
6. Test coverage gaps where critical code paths have no corresponding test file (use file listing — if `src/X/foo.py` exists but `tests/X/foo.test.py` doesn't, that may be drift toward "tests not maintained").

Discipline:
- NEVER fabricate. Cite the file path / commit hash / line range.
- The "File listing" section is AUTHORITATIVE for what exists. If a file is not in the listing, it does not exist.
- The "Entry-point files" section has full content for index/manifest/init files. Use it to confirm declared vs. delivered features.
- A drift finding should be reconstructible from the input — point to the specific evidence the reviewer can verify.
- Distinguish observable drift from theoretical drift. README says "we encrypt X" + no encryption code visible = observable. README says "we will encrypt X (v2)" + no v2 yet = not drift (it's roadmap).

Severity:
- P0 — README directly contradicts shipped behavior in a way that could mislead a reader (e.g., "we encrypt X" — no encryption code visible)
- P1 — high TODO count without paydown, broken doc links, version contradictions, commented-out code blocks left behind
- P2 — minor staleness (one stale link, one out-of-date example in docs)

For each finding:
- If confidence < 0.6, you MUST include a non-empty `uncertainty_reason` field.
- If the finding asserts a file or feature is missing, set `absence_claim: true` and state which authoritative section you checked.

Output ONE JSON object exactly. Schema same as code_quality lens, with `lens: "drift"`.
"""


def run(
    ctx: RepoContext,
    client: anthropic.Anthropic,
    tracker: CostTracker | None = None,
    model: str | None = None,
) -> list[Finding]:
    model = model or MODEL
    user = build_repo_prompt(ctx)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    if tracker is not None:
        record_response(tracker, response, model=model, lens_name=LENS_NAME)
    text = "".join(getattr(b, "text", "") for b in response.content)
    return parse_findings(text, LENS_NAME)
