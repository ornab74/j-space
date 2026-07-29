#!/usr/bin/env python3
"""Inject the Humoid V7 repository-management installer into the V6 notebook.

Usage:
    python tools/inject_humoid_v7_notebook.py \
      Humoid_Weaviate_V6_MEMORY_HIT_SCHEMA_FIXED_\(1\).ipynb \
      Humoid_Weaviate_V7_REPO_MANAGEMENT_FIXED.ipynb
"""

from __future__ import annotations

from pathlib import Path
import argparse
import ast
import hashlib
import json

import nbformat


INSTALL_CELL_MARKER = "#@title 10DI. Install Humoid V7 repository management"

INSTALL_SOURCE = r'''#@title 10DI. Install Humoid V7 repository management
from pathlib import Path
import importlib.util
import urllib.request

V7_MODULE_URL = (
    "https://raw.githubusercontent.com/ornab74/j-space/"
    "fix/v7-repo-management/humoid_v7_repo_management.py"
)
V7_MODULE_PATH = Path("/content/humoid_v7_repo_management.py")
urllib.request.urlretrieve(V7_MODULE_URL, V7_MODULE_PATH)

spec = importlib.util.spec_from_file_location(
    "humoid_v7_repo_management",
    V7_MODULE_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to import {V7_MODULE_PATH}")
humoid_v7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(humoid_v7)

CODING_REPO_PACKAGE_NAME = "humoid_quantum" #@param {type:"string"}
CODE_REPO_SOURCE_URL = "" #@param {type:"string"}
CODE_REPO_SOURCE_REF = "main" #@param {type:"string"}
CODING_REPO_CREATE_BASELINE_COMMIT = True #@param {type:"boolean"}

V7_REPORT = humoid_v7.install_humoid_v7(
    globals(),
    reset_invalid_state=True,
)
'''

GUIDE_SOURCE = '''### Humoid V7 repository management

This cell initializes a real repository before the coding DAG is compiled.

- Empty target: creates a `src/` package, tests, `pyproject.toml`, Git history,
  and a baseline commit.
- Existing target: preserves all files and indexes the existing repository.
- Clone mode: set `CODE_REPO_SOURCE_URL` while the target directory is empty.
- Candidate paths are repository-relative.
- New files use `/dev/null` patch headers.
- Invalid pre-V7 scheduler state is archived before a fresh DAG is compiled.

After the V7 installer runs, rerun cells 11B, 11C, 11A, and the scheduler.
'''


def find_insert_index(notebook) -> int:
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        if "#@title 11B. Initialize and inspect the coding repository" in cell.source:
            return index
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type == "code" and "#@title 11. Run/resume" in cell.source:
            return index
    return len(notebook.cells)


def validate_python_cells(notebook) -> list[dict[str, object]]:
    failures = []
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        if any(line.lstrip().startswith(("!", "%")) for line in cell.source.splitlines()):
            continue
        try:
            ast.parse(cell.source)
        except SyntaxError as exc:
            failures.append(
                {
                    "cell": index,
                    "line": exc.lineno,
                    "message": exc.msg,
                }
            )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    notebook = nbformat.read(args.input, as_version=4)
    notebook.cells = [
        cell
        for cell in notebook.cells
        if INSTALL_CELL_MARKER not in getattr(cell, "source", "")
    ]

    index = find_insert_index(notebook)
    notebook.cells.insert(index, nbformat.v4.new_markdown_cell(GUIDE_SOURCE))
    notebook.cells.insert(index + 1, nbformat.v4.new_code_cell(INSTALL_SOURCE))

    nbformat.validate(notebook)
    failures = validate_python_cells(notebook)
    if failures:
        raise RuntimeError(
            "Notebook Python validation failed:\n"
            + json.dumps(failures, indent=2)
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, args.output)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"Created: {args.output}")
    print(f"Cells:   {len(notebook.cells)}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
