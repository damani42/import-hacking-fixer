#!/usr/bin/env python3
"""Core utilities for import-hacking-fixer.
This module provides functions to classify and normalize import statements,
detect issues with import order, and fix them in Python files. It also exposes
functions to discover project packages and standard library modules.
"""

from __future__ import annotations

import ast
import logging
import sys
import sysconfig
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple


def get_stdlib_modules() -> Set[str]:
    """Return a set of top-level standard library module names."""
    # Use sysconfig to get the standard library directory and include built-in modules
    stdlib_dir = Path(sysconfig.get_paths()["stdlib"])
    modules: Set[str] = set(sys.builtin_module_names)
    for entry in stdlib_dir.iterdir():
        name = entry.stem
        if entry.is_file() and entry.suffix == '.py':
            modules.add(name)
        elif entry.is_dir() and (entry / '__init__.py').exists():
            modules.add(name)
    return modules


def find_project_packages(start: Path) -> Set[str]:
    """Discover project packages by walking from the given start directory.

    It searches for directories containing an __init__.py file and treats them
    as package roots. Returns a set of top-level package names.
    """
    pkgs: Set[str] = set()
    for path in start.rglob('__init__.py'):
        try:
            rel = path.relative_to(start)
        except ValueError:
            continue
        parts = rel.parts
        if parts:
            pkgs.add(parts[0])
    return pkgs


def classify_import(module: Optional[str], stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify an import module as 'stdlib', 'third_party', or 'project'."""
    if not module:
        return 'stdlib'
    root = module.split('.')[0]
    if root in stdlib:
        return 'stdlib'
    if root in project_pkgs:
        return 'project'
    return 'third_party'


def normalize_import(module: Optional[str], name: str, import_type: str) -> str:
    """Return the normalized import string."""
    if import_type == 'from' and module:
        return f"from {module} import {name}"
    return f"import {name}"


def process_imports(tree: ast.AST, stdlib: Set[str], project_pkgs: Set[str]) -> List[str]:
    """Process import statements in the AST, return sorted normalized imports."""
    imports_list: List[Tuple[str, Optional[str], str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            category = classify_import(node.module, stdlib, project_pkgs)
            for alias in node.names:
                imports_list.append((category, node.module, alias.name, "from"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                category = classify_import(alias.name, stdlib, project_pkgs)
                imports_list.append((category, None, alias.name, "import"))
    category_order = {"stdlib": 0, "third_party": 1, "project": 2}
    sorted_list = sorted(
        imports_list,
        key=lambda x: (
            category_order[x[0]],
            0 if x[3] == "from" else 1,
            f"{x[1]}.{x[2]}" if x[1] else x[2],
        ),
    )
    return [normalize_import(module, name, import_type) for (category, module, name, import_type) in sorted_list]


def process_file(file_path: Path, stdlib: Set[str], project_pkgs: Set[str]) -> Iterator[str]:
    """Read a Python file and yield lines with sorted imports in the correct order."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    tree = ast.parse(''.join(lines))
    imports = process_imports(tree, stdlib, project_pkgs)
    # Yield sorted imports followed by an empty line
    for imp in imports:
        yield imp
    yield ''
    # Now yield the rest of the lines, skipping original import statements
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            continue
        yield line.rstrip('\n')
