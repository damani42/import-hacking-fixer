#!/usr/bin/env python3
"""Core functions for import-hacking-fixer.

This module provides functions to analyze and fix import statements
according to OpenStack Hacking rules.
"""

import ast
from collections import defaultdict
import os
import sys
from typing import Dict, Iterable, List, Set, Tuple


def get_stdlib_modules() -> Set[str]:
    """Return a set of standard library module names."""
    stdlib: Set[str] = set()
    if hasattr(sys, "stdlib_module_names"):
        stdlib.update(sys.stdlib_module_names)  # type: ignore[attr-defined]
    else:
        stdlib.update(sys.builtin_module_names)
        libdir = os.path.dirname(os.__file__)
        for name in os.listdir(libdir):
            if name.endswith(".py") and name != "__init__.py":
                stdlib.add(name[:-3])
            elif os.path.isdir(os.path.join(libdir, name)):
                stdlib.add(name)
    return {mod.split(".")[0] for mod in stdlib}


def find_project_packages(root: str) -> Set[str]:
    """Detect first-level packages in the project by presence of __init__.py."""
    packages: Set[str] = set()
    for entry in os.listdir(root):
        path = os.path.join(root, entry)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "__init__.py")):
            packages.add(entry)
    return packages


def classify_import(module: str, stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify import as 'stdlib', 'project' or 'thirdparty'."""
    top = module.split(".")[0]
    if top in stdlib:
        return "stdlib"
    if top in project_pkgs:
        return "project"
    return "thirdparty"


def normalize_import(name: str, alias: str | None = None) -> str:
    """Return normalized import spec, including alias if present."""
    return name if alias is None else f"{name} as {alias}"


def process_imports(
    nodes: Iterable[ast.AST],
    stdlib: Set[str],
    project_pkgs: Set[str],
) -> Tuple[Dict[str, List[str]], List[Tuple[int, str]]]:
    """Process import and import-from nodes, grouping and sorting them."""
    groups: Dict[str, List[str]] = defaultdict(list)
    warnings: List[Tuple[int, str]] = []
    for node in nodes:
        if isinstance(node, ast.Import):
            if len(node.names) > 1:
                warnings.append((node.lineno, "H301: multiple modules on one import line"))
            for alias in node.names:
                mod = alias.name
                key = classify_import(mod, stdlib, project_pkgs)
                groups[key].append(normalize_import(mod, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            if node.level and node.level > 0:
                warnings.append(
                    (
                        node.lineno,
                        f"H304: relative import detected: 'from {'.' * node.level}{node.module or ''} import ...'",
                    )
                )
                continue
            base_mod = node.module or ""
            if len(node.names) > 1:
                warnings.append((node.lineno, f"H301: multiple names imported from '{base_mod}' on one line"))
            for alias in node.names:
                if alias.name == "*":
                    warnings.append((node.lineno, f"H303: wildcard import detected from '{base_mod}'"))
                    continue
                full_name = f"{base_mod}.{alias.name}" if base_mod else alias.name
                key = classify_import(base_mod, stdlib, project_pkgs)
                groups[key].append(normalize_import(full_name, alias.asname))
    for key in groups:
        groups[key] = sorted(groups[key], key=lambda x: x.lower())
    return groups, warnings


def rewrite_imports(original_lines: List[str], groups: Dict[str, List[str]]) -> List[str]:
    """Compose a new import block from grouped imports."""
    new_import_lines: List[str] = []
    order = ["stdlib", "thirdparty", "project"]
    for group in order:
        if groups.get(group):
            for imp in groups[group]:
                if "." in imp:
                    parts = imp.split(" as ")
                    name_part = parts[0]
                    alias_part = parts[1] if len(parts) == 2 else None
                    pkg, sub = name_part.rsplit(".", 1)
                    if alias_part:
                        new_import_lines.append(f"from {pkg} import {sub} as {alias_part}\n")
                    else:
                        new_import_lines.append(f"from {pkg} import {sub}\n")
                else:
                    new_import_lines.append(f"import {imp}\n")
            new_import_lines.append("\n")
    return new_import_lines


def find_import_block(lines: List[str]) -> Tuple[int, int]:
    """Find the start and end indices of the import block at the top of the file."""
    start: int | None = None
    end: int | None = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            if start is None:
                start = idx
            end = idx
        elif start is not None and stripped == "":
            end = idx
        elif start is not None:
            break
    if start is None or end is None:
        return (-1, -1)
    return (start, end)


def process_file(
    path: str,
    stdlib: Set[str],
    project_pkgs: Set[str],
    apply: bool = False,
) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a single Python file. Returns (modified, warnings)."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    tree = ast.parse("".join(lines), filename=path)
    import_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    groups, warnings = process_imports(import_nodes, stdlib, project_pkgs)
    if not import_nodes:
        return (False, warnings)
    start, end = find_import_block(lines)
    if start == -1:
        return (False, warnings)
    new_imports = rewrite_imports(lines[start : end + 1], groups)
    new_content = "".join(new_imports) + "".join(lines[end + 1 :])
    original_content = "".join(lines)
    modified = new_content != original_content
    if modified and apply:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    return (modified, warnings)


def iter_python_files(path: str) -> Iterable[str]:
    """Iterate recursively over Python files under a path."""
    if os.path.isdir(path):
        for root, _, filenames in os.walk(path):
            for fn in filenames:
                if fn.endswith(".py"):
                    yield os.path.join(root, fn)
    else:
        if path.endswith(".py"):
            yield path
