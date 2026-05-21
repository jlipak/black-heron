"""Repo discovery — walk files, detect entry-points, parse git log, build context bundle."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable

from ._models import EntryPoint, RepoContext

DEFAULT_IGNORES = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "audit_output", "coverage",
}

SOURCE_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".swift", ".kt",
    ".sh", ".md", ".sql", ".html", ".css",
}

CONFIG_EXT = {".json", ".yaml", ".yml", ".toml"}

MAX_SAMPLE_BYTES = 4000
ENTRY_POINT_BYTE_CAP = 10000  # full content cap per entry point (~200 lines)
TODO_PATTERN = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")

LANG_MAP = {
    ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".py": "Python", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin",
    ".c": "C", ".cpp": "C++", ".h": "C", ".hpp": "C++",
}

# Entry-point detection: (filename pattern, role)
# Matching is by basename (case-insensitive) for most; some by full relative-path suffix.
ENTRY_POINT_BASENAMES: list[tuple[str, str]] = [
    # Package manifests — declare intent + dependencies
    ("package.json", "package_manifest"),
    ("pyproject.toml", "package_manifest"),
    ("Cargo.toml", "package_manifest"),
    ("go.mod", "package_manifest"),
    ("setup.py", "package_manifest"),
    ("setup.cfg", "package_manifest"),
    ("requirements.txt", "package_manifest"),
    # Language configs — strict mode, target version, paths
    ("tsconfig.json", "language_config"),
    ("ruff.toml", "language_config"),
    ("mypy.ini", "language_config"),
    (".eslintrc.json", "language_config"),
    # Build configs
    ("vite.config.ts", "build_config"),
    ("vite.config.js", "build_config"),
    ("next.config.ts", "build_config"),
    ("next.config.js", "build_config"),
    ("webpack.config.js", "build_config"),
    # Module/server entry-points
    ("index.ts", "module_init"),
    ("index.js", "module_init"),
    ("__init__.py", "module_init"),
    ("main.py", "cli_entry"),
    ("cli.py", "cli_entry"),
    ("__main__.py", "cli_entry"),
    ("main.go", "cli_entry"),
    ("main.rs", "cli_entry"),
    ("server.ts", "server_entry"),
    ("server.js", "server_entry"),
    ("server.py", "server_entry"),
    ("app.py", "server_entry"),
    ("app.ts", "server_entry"),
]

# Suffix-based entry points (e.g., any *.rubric.json is a policy file)
ENTRY_POINT_SUFFIXES: list[tuple[str, str]] = [
    (".rubric.json", "rubric_or_policy"),
    ("-rubric.json", "rubric_or_policy"),
    ("/rubric.json", "rubric_or_policy"),
    ("/rules.json", "rubric_or_policy"),
    ("/policy.json", "rubric_or_policy"),
]


def _is_text_file(p: Path) -> bool:
    suf = p.suffix.lower()
    return suf in SOURCE_EXT or suf in CONFIG_EXT


def _walk(repo: Path, ignores: set[str]) -> Iterable[Path]:
    for p in repo.rglob("*"):
        if any(part in ignores for part in p.parts):
            continue
        if p.is_file():
            yield p


def _git_log(repo: Path, n: int = 30) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "log", f"-{n}", "--oneline", "--no-color"],
            cwd=repo, stderr=subprocess.DEVNULL, text=True, timeout=10,
        )
        return out.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []


def _detect_language(files: list[Path]) -> str:
    counts: dict[str, int] = {}
    for f in files:
        counts[f.suffix.lower()] = counts.get(f.suffix.lower(), 0) + 1
    best = sorted(
        ((c, ext) for ext, c in counts.items() if ext in LANG_MAP),
        reverse=True,
    )
    return LANG_MAP[best[0][1]] if best else "mixed"


def _count_todos(files: Iterable[Path]) -> int:
    n = 0
    for f in files:
        if f.suffix.lower() not in SOURCE_EXT:
            continue
        try:
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                if TODO_PATTERN.search(line):
                    n += 1
        except OSError:
            continue
    return n


def _detect_entry_role(rel_path: str) -> str | None:
    name = rel_path.split("/")[-1].lower()
    posix = "/" + rel_path.replace("\\", "/").lower()
    for pat, role in ENTRY_POINT_BASENAMES:
        if name == pat.lower():
            return role
    for suf, role in ENTRY_POINT_SUFFIXES:
        if posix.endswith(suf.lower()):
            return role
    return None


def _load_entry_points(repo: Path, text_files: list[Path]) -> list[EntryPoint]:
    out: list[EntryPoint] = []
    seen_paths: set[str] = set()
    for f in text_files:
        rel = str(f.relative_to(repo)).replace("\\", "/")
        if rel in seen_paths:
            continue
        role = _detect_entry_role(rel)
        if role is None:
            continue
        try:
            data = f.read_bytes()
        except OSError:
            continue
        truncated = len(data) > ENTRY_POINT_BYTE_CAP
        body = data[:ENTRY_POINT_BYTE_CAP].decode("utf-8", errors="ignore")
        out.append(EntryPoint(path=rel, role=role, content=body, truncated=truncated))  # type: ignore[arg-type]
        seen_paths.add(rel)
    return out


def build_context(
    repo_path: Path,
    max_sample_files: int = 30,
    extra_ignores: list[str] | None = None,
) -> RepoContext:
    repo = repo_path.resolve()
    if not repo.is_dir():
        raise NotADirectoryError(f"Not a directory: {repo}")

    ignores = set(DEFAULT_IGNORES)
    if extra_ignores:
        ignores.update(extra_ignores)

    all_files = list(_walk(repo, ignores))
    text_files = [f for f in all_files if _is_text_file(f)]

    samples: dict[str, str] = {}
    for f in text_files:
        if len(samples) >= max_sample_files:
            break
        try:
            data = f.read_bytes()
            if len(data) > MAX_SAMPLE_BYTES:
                continue
            samples[str(f.relative_to(repo))] = data.decode("utf-8", errors="ignore")
        except OSError:
            continue

    entry_points = _load_entry_points(repo, text_files)

    return RepoContext(
        path=str(repo),
        file_count=len(text_files),
        primary_language=_detect_language(text_files),
        file_listing=sorted(str(f.relative_to(repo)) for f in text_files),
        sample_files=samples,
        entry_points=entry_points,
        git_log_recent=_git_log(repo),
        todo_count=_count_todos(text_files),
    )
