from .blind_spot import run as run_blind_spot
from .code_quality import run as run_code_quality
from .drift import run as run_drift
from .governance import run as run_governance

# HETEROGENEOUS REGISTRY — DO NOT iterate this dict and call values uniformly.
# `code_quality`, `governance`, `drift` accept (ctx, client, tracker?) -> list[Finding].
# `blind_spot` accepts (ctx, findings_so_far, client, tracker?) -> list[Finding].
# Callers must special-case `blind_spot` (see cli.py first_pass / cli.py blind_spot block,
# mcp_server.py audit_repository tool). To remove this asymmetry in v1.2, introduce a
# uniform Lens protocol class that accepts ctx + LensContext (which carries prior findings
# when relevant) and refactor all 4 lens modules to match.
ALL_LENSES = {
    "code_quality": run_code_quality,
    "governance": run_governance,
    "drift": run_drift,
    "blind_spot": run_blind_spot,
}

FIRST_PASS_LENSES = ("code_quality", "governance", "drift")
SECOND_PASS_LENSES = ("blind_spot",)
