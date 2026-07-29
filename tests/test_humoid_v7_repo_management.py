from pathlib import Path
from types import SimpleNamespace
import json

import humoid_v7_repo_management as v7


def test_normalize_repo_path_under_root(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    assert v7.normalize_repo_path(root / "src/pkg/core.py", root) == "src/pkg/core.py"
    assert v7.normalize_repo_path("a/src/pkg/core.py", root) == "src/pkg/core.py"
    assert v7.normalize_repo_path("b/tests/test_core.py", root) == "tests/test_core.py"


def test_normalize_repo_path_rejects_escape(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    try:
        v7.normalize_repo_path("../outside.py", root)
    except ValueError as exc:
        assert "Unsafe repository path" in str(exc)
    else:
        raise AssertionError("path escape was accepted")


def test_greenfield_repository_bootstrap(tmp_path: Path):
    root = tmp_path / "repo"
    mode, created, commit, initialized = v7.initialize_managed_repository(
        root,
        package_name="Quantum Core",
        create_baseline_commit=True,
    )

    assert mode == "greenfield"
    assert initialized is True
    assert (root / ".git").is_dir()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src/quantum_core/__init__.py").is_file()
    assert (root / "tests/test_repository_bootstrap.py").is_file()
    assert "pyproject.toml" in created
    assert commit


def test_existing_repository_is_preserved(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    original = root / "existing.txt"
    original.write_text("preserve me", encoding="utf-8")

    mode, created, _, _ = v7.initialize_managed_repository(
        root,
        package_name="example",
    )

    assert mode == "existing"
    assert created == []
    assert original.read_text(encoding="utf-8") == "preserve me"


def test_absolute_candidate_paths_are_normalized(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    source = f'''# CHANGESET_MANIFEST
```json
{{"files_created":["{root}/src/pkg/core.py"]}}
```
# Patch
```diff
--- /dev/null
+++ b/{root}/src/pkg/core.py
@@ -0,0 +1 @@
+VALUE = 1
```
'''
    normalized = v7.normalize_candidate_text(source, root)
    assert str(root) not in normalized
    assert "src/pkg/core.py" in normalized


def test_invalid_scheduler_state_is_archived(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps(
            {
                "tasks": {
                    "task-1": {
                        "read_paths": [],
                        "write_paths": [str(root / "absolute.py")],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    namespace = {"AUTONOMOUS_STATE_PATH": state}
    archived = v7._archive_invalid_state(namespace, root)
    assert archived
    assert Path(archived).is_file()
    assert not state.exists()
