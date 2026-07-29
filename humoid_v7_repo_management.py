"""Humoid V7 repository initialization and patch-management hotfix.

Run this after the V6 classes and CODE_REPO_ROOT configuration are loaded:

    from humoid_v7_repo_management import install_humoid_v7
    V7_REPORT = install_humoid_v7(globals(), reset_invalid_state=True)

The module repairs greenfield repository bootstrapping, repository-relative path
handling, first-slice repetition false positives, new-file patch contracts, and
stranded scheduler state. It is intentionally conservative: verified patches
remain sandbox-only unless the notebook's existing transaction controls enable
application.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
from typing import Any, MutableMapping
import contextlib
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess


@dataclass
class V7InstallReport:
    repository_root: str
    mode: str
    package_name: str
    initialized_git: bool
    bootstrapped_files: list[str]
    baseline_commit: str
    archived_state: str
    patched_classes: list[str]
    warnings: list[str]


def _run(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout={result.stdout[-4000:]}\n"
            f"stderr={result.stderr[-4000:]}"
        )
    return result


def _safe_package_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip()).strip("_")
    if not value:
        value = "humoid_quantum"
    if value[0].isdigit():
        value = "pkg_" + value
    return value.lower()


def normalize_repo_path(value: Any, root: Path | None = None) -> str:
    """Return a safe repository-relative POSIX path.

    Absolute paths under root, `a/` and `b/` diff prefixes, and leading `./`
    are normalized. Paths escaping the repository are rejected.
    """
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw == "/dev/null":
        return raw

    if root is not None:
        root_text = root.resolve().as_posix().rstrip("/")
        if raw == root_text:
            return ""
        if raw.startswith(root_text + "/"):
            raw = raw[len(root_text) + 1 :]

    raw = re.sub(r"^(?:\./)+", "", raw)
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]

    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe repository path: {value!r}")
    normalized = path.as_posix().lstrip("/")
    if not normalized or normalized == ".":
        raise ValueError(f"Empty repository path: {value!r}")
    return normalized


def _write_if_missing(root: Path, relative: str, content: str) -> bool:
    target = root / relative
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return True


def _tracked_or_source_files(root: Path) -> list[Path]:
    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "build", "dist"}
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in ignored for part in path.parts)
    ]


def initialize_managed_repository(
    root: Path,
    *,
    package_name: str = "humoid_quantum",
    source_url: str = "",
    source_ref: str = "main",
    create_baseline_commit: bool = True,
) -> tuple[str, list[str], str, bool]:
    """Initialize an existing clone or a valid greenfield Python repository."""
    root = root.expanduser().resolve()
    package_name = _safe_package_name(package_name)
    source_url = str(source_url or "").strip()
    source_ref = str(source_ref or "main").strip() or "main"
    root.mkdir(parents=True, exist_ok=True)

    non_git_entries = [path for path in root.iterdir() if path.name != ".git"]
    mode = "existing" if non_git_entries else "greenfield"

    if source_url and not non_git_entries:
        parent = root.parent
        temporary = parent / f".{root.name}.clone-v7"
        if temporary.exists():
            shutil.rmtree(temporary)
        _run(
            ["git", "clone", "--branch", source_ref, "--single-branch", source_url, str(temporary)],
            cwd=parent,
        )
        for child in temporary.iterdir():
            shutil.move(str(child), str(root / child.name))
        temporary.rmdir()
        mode = "clone"

    initialized_git = False
    if not (root / ".git").exists():
        _run(["git", "init"], cwd=root)
        initialized_git = True

    with contextlib.suppress(Exception):
        _run(["git", "config", "user.name", "Humoid V7"], cwd=root)
        _run(["git", "config", "user.email", "humoid-v7@localhost"], cwd=root)

    created: list[str] = []
    if mode == "greenfield":
        skeleton = {
            ".gitignore": "__pycache__/\n*.py[cod]\n.pytest_cache/\n.venv/\ndist/\nbuild/\n.coverage\n",
            "README.md": (
                f"# {package_name}\n\n"
                "Managed greenfield repository initialized by Humoid V7.\n\n"
                "Source code lives under `src/`; tests live under `tests/`.\n"
            ),
            "pyproject.toml": (
                "[build-system]\n"
                "requires = [\"setuptools>=68\"]\n"
                "build-backend = \"setuptools.build_meta\"\n\n"
                "[project]\n"
                f"name = \"{package_name.replace('_', '-')}\"\n"
                "version = \"0.1.0\"\n"
                "requires-python = \">=3.10\"\n"
                "dependencies = [\"numpy>=1.24\"]\n\n"
                "[tool.pytest.ini_options]\n"
                "testpaths = [\"tests\"]\n"
                "pythonpath = [\"src\"]\n"
                "addopts = \"-q\"\n\n"
                "[tool.setuptools.packages.find]\n"
                "where = [\"src\"]\n"
            ),
            f"src/{package_name}/__init__.py": (
                '"""Humoid-managed package root."""\n\n'
                '__all__: list[str] = []\n'
            ),
            "tests/__init__.py": "",
            "tests/test_repository_bootstrap.py": (
                f"def test_package_importable():\n"
                f"    import {package_name}\n"
                f"    assert {package_name}.__name__ == \"{package_name}\"\n"
            ),
        }
        for relative, content in skeleton.items():
            if _write_if_missing(root, relative, content):
                created.append(relative)

    baseline_commit = ""
    if create_baseline_commit and created:
        _run(["git", "add", "-A"], cwd=root)
        commit = _run(
            ["git", "commit", "-m", "Initialize Humoid V7 managed repository"],
            cwd=root,
            check=False,
        )
        if commit.returncode == 0:
            baseline_commit = _run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()

    return mode, created, baseline_commit, initialized_git


def _archive_invalid_state(namespace: MutableMapping[str, Any], root: Path) -> str:
    state_value = namespace.get("AUTONOMOUS_STATE_PATH")
    if not state_value:
        return ""
    state_path = Path(state_value)
    if not state_path.exists():
        return ""

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}

    tasks = dict(payload.get("tasks", {}))
    bad = False
    root_text = root.as_posix()
    for task in tasks.values():
        scopes = [
            *list(task.get("read_paths", []) or []),
            *list(task.get("write_paths", []) or []),
        ]
        if any(str(path).startswith(root_text + "/") or str(path).startswith("/") for path in scopes):
            bad = True
            break
    if not bad:
        return ""

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = state_path.with_name(state_path.name + f".pre-v7-{stamp}.bak")
    shutil.copy2(state_path, backup)
    state_path.unlink()
    return str(backup)


def _normalize_manifest_paths(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    value = dict(manifest)
    for key in ("files_modified", "files_created", "files_deleted"):
        value[key] = [
            normalize_repo_path(path, root)
            for path in (value.get(key, []) or [])
            if str(path or "").strip()
        ]
    normalized_reads = []
    for item in value.get("files_read", []) or []:
        if isinstance(item, dict):
            copied = dict(item)
            copied["path"] = normalize_repo_path(copied.get("path", ""), root)
            normalized_reads.append(copied)
        else:
            normalized_reads.append({"path": normalize_repo_path(item, root), "sha256": ""})
    value["files_read"] = normalized_reads
    return value


def normalize_candidate_text(text: str, root: Path) -> str:
    """Normalize absolute repository paths without inventing patch hunks."""
    root_text = root.resolve().as_posix().rstrip("/")
    text = str(text or "").replace(root_text + "/", "")
    text = re.sub(r"(?m)^(---|\+\+\+)\s+[ab]/(?:\./)+", r"\1 a/", text)
    return text


def _patch_classes(namespace: MutableMapping[str, Any], root: Path) -> list[str]:
    patched: list[str] = []

    manager_cls = namespace.get("CodingRepositoryManager")
    if manager_cls is not None and not getattr(manager_cls, "_humoid_v7_patched", False):
        original_ensure = manager_cls.ensure
        original_direct_context = manager_cls.direct_context
        original_validate = manager_cls.validate_candidate

        def ensure(self):
            original_ensure(self)
            package = _safe_package_name(namespace.get("CODING_REPO_PACKAGE_NAME", "humoid_quantum"))
            initialize_managed_repository(
                Path(self.root),
                package_name=package,
                source_url=str(namespace.get("CODE_REPO_SOURCE_URL", "")),
                source_ref=str(namespace.get("CODE_REPO_SOURCE_REF", "main")),
                create_baseline_commit=bool(namespace.get("CODING_REPO_CREATE_BASELINE_COMMIT", True)),
            )

        def direct_context(self, task):
            base = original_direct_context(self, task)
            absent = []
            for raw in getattr(task, "write_paths", ()) or ():
                try:
                    relative = normalize_repo_path(raw, Path(self.root))
                except ValueError:
                    continue
                if not (Path(self.root) / relative).exists():
                    absent.append(relative)
            if absent:
                contract = [
                    "# GREENFIELD FILE CONTRACT",
                    "The following repository-relative paths are absent and MUST be created as new files:",
                    *[f"- `{path}`: use `--- /dev/null` and `+++ b/{path}` with a `@@ -0,0 +... @@` hunk" for path in absent],
                    "List them under CHANGESET_MANIFEST.files_created, never files_modified.",
                    "Do not assume prior lines, stubs, hashes, or symbols for absent files.",
                ]
                return base + "\n\n" + "\n".join(contract)
            return base

        def validate_candidate(self, task, text):
            normalized_text = normalize_candidate_text(text, Path(self.root))
            report = original_validate(self, task, normalized_text)
            report["normalized_candidate_text"] = normalized_text
            report.setdefault("warnings", [])
            report.setdefault("errors", [])

            manifest = self._manifest_from_output(normalized_text)
            if manifest is not None:
                try:
                    manifest = _normalize_manifest_paths(manifest, Path(self.root))
                    report["normalized_manifest"] = manifest
                except ValueError as exc:
                    report["errors"].append(str(exc))

            diff_text = self._diff_from_output(normalized_text)
            changed = self.changed_paths(diff_text)
            for path in changed:
                target = Path(self.root) / path
                is_new_header = bool(
                    re.search(
                        rf"(?m)^---\s+/dev/null\s*$\n\+\+\+\s+b/{re.escape(path)}\s*$",
                        diff_text,
                    )
                )
                if target.exists() and is_new_header:
                    report["errors"].append(f"existing file declared as new: {path}")
                if not target.exists() and not is_new_header:
                    report["errors"].append(
                        f"absent file must use a /dev/null new-file patch: {path}"
                    )

            report["hard_fail"] = bool(report.get("hard_fail") or report["errors"])
            return report

        manager_cls.ensure = ensure
        manager_cls.direct_context = direct_context
        manager_cls.validate_candidate = validate_candidate
        manager_cls.normalize_repo_path = staticmethod(normalize_repo_path)
        manager_cls._humoid_v7_patched = True
        patched.append("CodingRepositoryManager")

    v6_cls = namespace.get("SoftwareEngineeringOrchestratorV6")
    if v6_cls is not None and not getattr(v6_cls, "_humoid_v7_patched", False):
        original_candidate_prompt = v6_cls._candidate_prompt
        original_generate = v6_cls._generate_candidate

        def candidate_prompt(self, **kwargs):
            system, user = original_candidate_prompt(self, **kwargs)
            root_path = Path(self.coding_repo.root).resolve() if self.coding_repo else root
            strict = f"""

V7 REPOSITORY MANAGEMENT CONTRACT
- Repository root: {root_path}
- Every manifest and diff path MUST be repository-relative; never emit `/content/...` paths.
- Existing files go in files_modified and require exact source hashes.
- Absent files go in files_created and MUST use `--- /dev/null`, `+++ b/<relative-path>`, and a new-file hunk beginning at zero.
- CHANGESET_MANIFEST must be strict JSON: no comments, ellipses, placeholder hashes, or trailing commas.
- Never assume an absent file contains stubs or line ranges.
- Any behavior implementation must include a real test file in the same patch.
- Never add placeholder classes, ImportError mocks, dummy optimizer values, pass/TODO/FIXME, or fake test claims.
""".rstrip()
            return system + strict, user

        def generate_candidate(self, **kwargs):
            text = original_generate(self, **kwargs)
            root_path = Path(self.coding_repo.root).resolve() if self.coding_repo else root
            return normalize_candidate_text(text, root_path)

        v6_cls._candidate_prompt = candidate_prompt
        v6_cls._generate_candidate = generate_candidate
        v6_cls._humoid_v7_patched = True
        patched.append("SoftwareEngineeringOrchestratorV6")

    v5_cls = namespace.get("SoftwareEngineeringOrchestratorV5")
    if v5_cls is not None and not getattr(v5_cls, "_humoid_v7_repetition_patched", False):
        original_validation = v5_cls._deterministic_validation

        def deterministic_validation(self, task, chunk):
            report = original_validation(self, task, chunk)
            if int(getattr(task, "slices", 0) or 0) <= 1:
                repeat_prefixes = (
                    "slice repeats prior work at similarity",
                    "first slice repeats prior work",
                )
                report["errors"] = [
                    error
                    for error in report.get("errors", [])
                    if not str(error).lower().startswith(repeat_prefixes)
                ]
                report["cycle_similarity"] = 0.0
                report["cycle_novelty"] = 1.0
                report["hard_fail"] = bool(
                    report.get("errors")
                    or not report.get("syntax_ok", True)
                    or report.get("runtime_ok") is False
                    or report.get("coding", {}).get("hard_fail", False)
                )
            return report

        v5_cls._deterministic_validation = deterministic_validation
        v5_cls._humoid_v7_repetition_patched = True
        patched.append("SoftwareEngineeringOrchestratorV5")

    return patched


def install_humoid_v7(
    namespace: MutableMapping[str, Any],
    *,
    reset_invalid_state: bool = True,
) -> dict[str, Any]:
    """Install V7 fixes into a running Humoid V6 Colab namespace."""
    root = Path(namespace.get("CODE_REPO_ROOT", "/content/humoid_target_repo")).expanduser().resolve()
    package_name = _safe_package_name(namespace.get("CODING_REPO_PACKAGE_NAME", "humoid_quantum"))
    mode, created, baseline_commit, initialized_git = initialize_managed_repository(
        root,
        package_name=package_name,
        source_url=str(namespace.get("CODE_REPO_SOURCE_URL", "")),
        source_ref=str(namespace.get("CODE_REPO_SOURCE_REF", "main")),
        create_baseline_commit=bool(namespace.get("CODING_REPO_CREATE_BASELINE_COMMIT", True)),
    )

    namespace["CODING_REPO_PACKAGE_NAME"] = package_name
    namespace.setdefault("CODE_REPO_SOURCE_URL", "")
    namespace.setdefault("CODE_REPO_SOURCE_REF", "main")
    namespace.setdefault("CODING_REPO_CREATE_BASELINE_COMMIT", True)

    archived = _archive_invalid_state(namespace, root) if reset_invalid_state else ""
    patched = _patch_classes(namespace, root)

    warnings: list[str] = []
    if mode == "greenfield":
        warnings.append(
            "Greenfield baseline created. Rerun repository initialization, V6 services, and the scheduler so the graph includes the new files."
        )
    if archived:
        warnings.append(
            "An incompatible pre-V7 scheduler state was archived; resume will begin with a fresh task DAG."
        )

    report = V7InstallReport(
        repository_root=str(root),
        mode=mode,
        package_name=package_name,
        initialized_git=initialized_git,
        bootstrapped_files=created,
        baseline_commit=baseline_commit,
        archived_state=archived,
        patched_classes=patched,
        warnings=warnings,
    )
    result = asdict(report)
    print("=== Humoid V7 repository management ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


__all__ = [
    "V7InstallReport",
    "initialize_managed_repository",
    "install_humoid_v7",
    "normalize_candidate_text",
    "normalize_repo_path",
]
