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
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple


def get_stdlib_modules() -> Set[str]:
    """Return a set of top-level standard library module names."""
    stdlib_dir = Path(sys.modules['sys'].__file__).parent
    modules: Set[str] = set()
    for entry in stdlib_dir.iterdir():
        name = entry.stem
        if entry.is_file() and entry.suffix == '.py':
            modules.add(name)
        elif entry.is_dir() and (entry / '__init__.py').exists():
            modules.add(name)
    return modules


def find_project_packages(root: Path) -> Set[str]:
    """Return a set of top-level package names for the given project root."""
    packages: Set[str] = set()
    for item in root.iterdir():
        if item.is_dir() and (item / '__init__.py').exists():
            packages.add(item.name)
    return packages


def classify_import(module: str, stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify an import module into categories: 'stdlib', 'third_party', or 'project'."""
    root = module.split('.', 1)[0] if module else ''
    if root in stdlib:
        return 'stdlib'
    if root in project_pkgs:
        return 'project'
    return 'third_party'


def normalize_import(module: str, names: List[str]) -> str:
    """Normalize an import statement to a single-line representation."""
    if module:
        return f"from {module} import {', '.join(names)}"
    else:
        return f"import {', '.join(names)}"


def process_imports(tree: ast.AST, stdlib: Set[str], project_pkgs: Set[str]) -> Tuple[bool, List[str], List[Tuple[int, str]]]:
    """Process import nodes in the AST and build a sorted list of normalized imports and warnings.

    Returns a tuple (modified, new_import_lines, warnings).
    """
    imports_list: List[Tuple[str, str, str]] = []
    warnings: List[Tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # detect multiple names (H301)
            if len(node.names) > 1:
                warnings.append((node.lineno, "H301: one import per line"))
            for alias in node.names:
                name = alias.name
                # convert project package import with dot to from import
                if '.' in name:
                    root, rest = name.split('.', 1)
                    if root in project_pkgs:
                        category = classify_import(root, stdlib, project_pkgs)
                        imports_list.append((category, root, rest))
                        continue
                # normal import
                category = classify_import(name.split('.')[0], stdlib, project_pkgs)
                imports_list.append((category, '', name))
        elif isinstance(node, ast.ImportFrom):
            # relative import detection (H304)
            if getattr(node, 'level', 0):
                # Construct the relative import representation for message
                rel_prefix = '.' * node.level
                modname = node.module or ''
                warnings.append((node.lineno, f"H304: No relative imports. '{rel_prefix + modname}' is a relative import"))
                continue
            # wildcard detection (H303)
            if any(alias.name == '*' for alias in node.names):
                warnings.append((node.lineno, "H303: No wildcard (*) import."))
                continue
            # multiple names detection (H301)
            if len(node.names) > 1:
                warnings.append((node.lineno, "H301: one import per line"))
            module = node.module or ''
            for alias in node.names:
                name = alias.name
                category = classify_import(module, stdlib, project_pkgs)
                imports_list.append((category, module, name))

    if not imports_list:
        logging.debug("No import statements found.")
        return False, [], warnings

    # sort by category order and full module path
    category_order = {'stdlib': 0, 'third_party': 1, 'project': 2}
    sorted_list = sorted(
        imports_list,
        key=lambda x: (category_order[x[0]], f"{x[1]}.{x[2]}" if x[1] else x[2])
    )
    # deduplicate while preserving order and build new_lines
    new_lines: List[str] = []
    seen_keys: Set[Tuple[str, str, str]] = set()
    current_category: Optional[str] = None
    for category, module, name in sorted_list:
        key = (category, module, name)
        if key in seen_keys:
            continue
        if current_category is None:
            current_category = category
        elif category != current_category:
            # blank line to separate categories
            new_lines.append('')
            current_category = category
        new_lines.append(normalize_import(module, [name]))
        seen_keys.add(key)

    # Always finish with a blank line to separate imports from code
    new_lines.append('')

    # Always indicate that modification may be needed when there are warnings or reorderings
    modified = True
    return modified, new_lines, warnings


def rewrite_imports(lines: List[str], start: int, end: int, new_imports: List[str]) -> List[str]:
    """Rewrite the import block within lines[start:end] with new_imports."""
    return lines[:start] + new_imports + lines[end:]


def find_import_block(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Find the start and end indices of the contiguous block of import statements."""
    start: Optional[int] = None
    end: Optional[int] = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            if start is None:
                start = i
            end = i + 1
        elif start is not None and stripped:
            break
    return (start, end) if start is not None and end is not None else None


def process_file(file_path: str, stdlib: Set[str], project_pkgs: Set[str], apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a single Python file, check and fix import ordering and hacking rules.

    Returns (modified, warnings).
    """
    path_obj = Path(file_path)
    try:
        source = path_obj.read_text()
    except Exception as e:
        return False, [(0, f"Could not read file: {e}")]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, [(e.lineno or 0, f"Syntax error: {e.msg}")]
    modified, new_import_lines, import_warnings = process_imports(tree, stdlib, project_pkgs)
    # If no modifications suggested and no warnings, nothing to do
    if not modified and not import_warnings:
        return False, []
    lines = source.splitlines()
    block = find_import_block(lines)
    warnings: List[Tuple[int, str]] = import_warnings.copy()
    if block:
        start, end = block
        if apply:
            new_lines = rewrite_imports(lines, start, end, new_import_lines)
            try:
                path_obj.write_text('\n'.join(new_lines) + '\n')
            except Exception as e:
                warnings.append((0, f"Could not write file: {e}"))
                return False, warnings
            return True, warnings
        else:
            # add generic warning about reordering if modifications
            warnings.append((start + 1, "Imports are not ordered correctly."))
            return True, warnings
    else:
        warnings.append((0, "Import block could not be located."))
        return False, warnings


def iter_python_files(root: Path, ignore: Optional[Iterable[str]] = None) -> Iterator[Path]:
    """Yield Python files under the given root directory, excluding specified patterns."""
    ignore_set = set(ignore or [])
    for path in root.rglob('*.py'):
        if any(str(path).startswith(str(root / pattern)) for pattern in ignore_set):
            continue
        yield path
