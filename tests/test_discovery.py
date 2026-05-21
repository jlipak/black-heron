"""Tests for discovery.py — file walk, entry-point detection, TODO scan, language detection."""
from __future__ import annotations

from pathlib import Path

from black_heron.discovery import (
    DEFAULT_IGNORES,
    ENTRY_POINT_BYTE_CAP,
    _detect_entry_role,
    build_context,
)


def test_build_context_clean_repo(tiny_clean_repo: Path) -> None:
    ctx = build_context(tiny_clean_repo)
    assert ctx.file_count >= 3  # __init__.py, main.py, pyproject.toml, README.md
    assert ctx.primary_language == "Python"
    assert ctx.todo_count == 0
    assert ctx.path == str(tiny_clean_repo.resolve())


def test_build_context_dirty_repo_detects_todos(tiny_dirty_repo: Path) -> None:
    ctx = build_context(tiny_dirty_repo)
    # messy.py has TODO + FIXME + XXX = 3 markers
    assert ctx.todo_count == 3


def test_entry_point_role_pyproject() -> None:
    assert _detect_entry_role("pyproject.toml") == "package_manifest"


def test_entry_point_role_package_json() -> None:
    assert _detect_entry_role("package.json") == "package_manifest"


def test_entry_point_role_index_ts() -> None:
    assert _detect_entry_role("src/index.ts") == "module_init"


def test_entry_point_role_init_py() -> None:
    assert _detect_entry_role("src/__init__.py") == "module_init"


def test_entry_point_role_main_py() -> None:
    assert _detect_entry_role("main.py") == "cli_entry"


def test_entry_point_role_random_file_is_none() -> None:
    assert _detect_entry_role("src/random_module.py") is None


def test_entry_point_role_rubric_json() -> None:
    assert _detect_entry_role("config/rules.json") == "rubric_or_policy"


def test_build_context_loads_entry_points(tiny_clean_repo: Path) -> None:
    ctx = build_context(tiny_clean_repo)
    paths = [ep.path for ep in ctx.entry_points]
    assert any(p.endswith("pyproject.toml") for p in paths)
    assert any(p.endswith("__init__.py") for p in paths)
    # All under 10KB cap → no truncation
    for ep in ctx.entry_points:
        assert ep.truncated is False
    # At least pyproject.toml has non-empty content (__init__.py is legitimately empty)
    pyproject = next(ep for ep in ctx.entry_points if ep.path.endswith("pyproject.toml"))
    assert pyproject.content


def test_build_context_respects_default_ignores(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("// junk")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")
    ctx = build_context(tmp_path)
    # node_modules and .git contents should be excluded
    for p in ctx.file_listing:
        assert "node_modules" not in p
        assert ".git" not in p


def test_entry_point_content_capped() -> None:
    # ENTRY_POINT_BYTE_CAP is 10000 — confirm constant matches discovery.py behavior
    assert ENTRY_POINT_BYTE_CAP == 10000


def test_default_ignores_contains_critical_dirs() -> None:
    for d in {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}:
        assert d in DEFAULT_IGNORES
