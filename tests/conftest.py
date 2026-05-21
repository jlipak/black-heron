"""Shared pytest fixtures for Black Heron tests."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def tiny_clean_repo(tmp_path: Path) -> Path:
    """A minimal clean Python repo with no obvious issues — used for negative-path tests."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "src" / "main.py").write_text(textwrap.dedent("""
        '''Tiny example module.'''


        def add(a: int, b: int) -> int:
            return a + b
    """).strip() + "\n")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [project]
        name = "tiny-clean"
        version = "0.1.0"
    """).strip() + "\n")
    (tmp_path / "README.md").write_text("# Tiny clean repo\n")
    return tmp_path


@pytest.fixture
def tiny_dirty_repo(tmp_path: Path) -> Path:
    """A minimal repo with known issues — used for positive-path tests."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "messy.py").write_text(textwrap.dedent("""
        # TODO: refactor this whole module
        # FIXME: hardcoded secret below

        API_KEY = "should-be-env-var"

        def bad():
            # XXX: this never works
            pass
    """).strip() + "\n")
    (tmp_path / "package.json").write_text('{"name": "tiny-dirty", "version": "0.1.0"}\n')
    (tmp_path / "README.md").write_text("# Has secrets\n")
    return tmp_path
