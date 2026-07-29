# Humoid V7 repository initialization and patch management

This repair addresses the failures seen in `Humoid_Weaviate_V6_MEMORY_HIT_SCHEMA_FIXED_(1).ipynb` when `/content/humoid_target_repo` is empty:

- model manifests used absolute `/content/...` paths;
- absent files were emitted as modifications instead of new-file patches;
- the sandbox could not apply hunks against nonexistent files;
- tasks inherited invalid scopes from pre-bootstrap scheduler state;
- first slices could be compared with their own just-written artifact and marked repetitive;
- algorithm tasks started before a package, tests, and baseline commit existed.

## Run inside the existing notebook

After the V6 class-definition cells and before repository cell **11B**, add and run:

```python
#@title 10DI. Install Humoid V7 repository management
!wget -q \
  https://raw.githubusercontent.com/ornab74/j-space/fix/v7-repo-management/humoid_v7_repo_management.py \
  -O /content/humoid_v7_repo_management.py

from humoid_v7_repo_management import install_humoid_v7

# Greenfield defaults. Set CODE_REPO_SOURCE_URL for an existing Git repository.
CODING_REPO_PACKAGE_NAME = "humoid_quantum"
CODE_REPO_SOURCE_URL = ""
CODE_REPO_SOURCE_REF = "main"
CODING_REPO_CREATE_BASELINE_COMMIT = True

V7_REPORT = install_humoid_v7(
    globals(),
    reset_invalid_state=True,
)
```

Then rerun:

1. **11B — Initialize and inspect the coding repository**
2. **11C — Initialize V6 repository operating-system services**
3. **11A — Quick Weaviate runtime check**
4. Scheduler with `resume=True`

When an incompatible pre-V7 scheduler state is detected, it is copied to a timestamped `.pre-v7-*.bak` file and the scheduler creates a new DAG from the initialized repository map.

## Greenfield mode

Leave the source URL empty:

```python
CODE_REPO_ROOT = "/content/humoid_target_repo"
CODE_REPO_SOURCE_URL = ""
CODING_REPO_PACKAGE_NAME = "humoid_quantum"
```

The manager creates:

```text
.gitignore
README.md
pyproject.toml
src/humoid_quantum/__init__.py
tests/__init__.py
tests/test_repository_bootstrap.py
```

It initializes Git, configures repository-local commit identity, and creates a baseline commit. The repository graph and Weaviate source index therefore start from real files rather than an empty Merkle tree.

## Existing repository mode

Point the manager at an existing clone:

```python
CODE_REPO_ROOT = "/content/my-project"
CODE_REPO_SOURCE_URL = ""
```

Or clone a public repository into an empty target directory:

```python
CODE_REPO_ROOT = "/content/humoid_target_repo"
CODE_REPO_SOURCE_URL = "https://github.com/owner/project.git"
CODE_REPO_SOURCE_REF = "main"
```

The clone occurs only when the target contains no non-Git files. Existing content is never deleted or overwritten by the bootstrapper.

## Enforced patch contract

V7 adds the following rules to every candidate prompt and deterministic validator:

1. Manifest and diff paths are repository-relative.
2. Existing files belong in `files_modified` and require actual source context.
3. Absent files belong in `files_created`.
4. New files use:

   ```diff
   --- /dev/null
   +++ b/src/humoid_quantum/example.py
   @@ -0,0 +1,20 @@
   +...
   ```

5. Strict JSON only: no comments, ellipses, fake hashes, or trailing commas.
6. No placeholder classes, fallback mocks, dummy optimization, `pass`, TODO, or fabricated test results.
7. Behavior changes include a real test file in the same patch.
8. The sandbox still rejects a patch that cannot apply to the exact repository state.

## Why `sandbox patch application failed` was correct

The rejected candidate used modification hunks such as:

```diff
--- a/quantum_core/complex.py
+++ b/quantum_core/complex.py
@@ -10,8 +10,34 @@
```

while the repository had zero files. There was no line 10 or existing blob to patch. V7 does not weaken the sandbox; it gives the coordinator and worker the correct greenfield contract and creates a real baseline before task generation.

## Safety

These V6 defaults remain unchanged:

```python
V6_AUTO_APPLY_VERIFIED_PATCH = False
V6_CREATE_GIT_COMMIT = False
```

Candidates are generated and sandbox-tested but are not applied to the target repository automatically unless those controls are deliberately enabled.
