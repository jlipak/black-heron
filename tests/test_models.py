"""Model policy tests — defaults, Law VIII differential, --budget-mode, --version. No API calls."""
from __future__ import annotations

from click.testing import CliRunner

from black_heron import __version__
from black_heron.cli import BUDGET_MODEL, LENS_MODELS, audit, resolve_lens_models
from black_heron.code_writer import VERIFIER_MODEL as PATCH_VERIFIER_MODEL
from black_heron.code_writer import WRITER_MODEL
from black_heron.cost_tracker import PRICES
from black_heron.synthesis import MODEL as VERIFIER_MODEL


def test_every_default_model_is_priced() -> None:
    for model in (*LENS_MODELS.values(), VERIFIER_MODEL, BUDGET_MODEL, WRITER_MODEL, PATCH_VERIFIER_MODEL):
        assert model in PRICES, model


def test_law_viii_verifier_runs_on_a_different_model_than_the_lenses() -> None:
    for lens, model in LENS_MODELS.items():
        assert model != VERIFIER_MODEL, lens
    assert WRITER_MODEL != PATCH_VERIFIER_MODEL


def test_law_ix_defaults_are_opus_and_budget_is_explicit() -> None:
    for model in (*LENS_MODELS.values(), VERIFIER_MODEL):
        assert model.startswith("claude-opus-"), model
    assert BUDGET_MODEL.startswith("claude-sonnet-")
    assert resolve_lens_models(budget_mode=False) == LENS_MODELS


def test_budget_mode_puts_every_lens_on_the_budget_model() -> None:
    resolved = resolve_lens_models(budget_mode=True)
    assert set(resolved) == set(LENS_MODELS)
    assert set(resolved.values()) == {BUDGET_MODEL}


def test_version_flag_prints_package_version() -> None:
    result = CliRunner().invoke(audit, ["--version"])
    assert result.exit_code == 0, result.output
    assert __version__ in result.output
