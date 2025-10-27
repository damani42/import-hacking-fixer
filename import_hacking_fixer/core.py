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
    """Return a set of top-level standard library module names.

    This inspects the directory of the Python standard library and built-in modules,
    and returns the names of .py files or packages (directories containing an ``__init__.py`` file).
    Only top-level modules are considered.

    Returns:
        A set of module names representing top-level standard library modules.
    """
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
    """Return a set of top-level package names for the given project root.

    Args:
        root: Path to project root directory.

    Returns:
        A set of names of directories under root that contain ``__init__.py``.
    """
    packages: Set[str] = set()
    for item in root.iterdir():
        if item.is_dir() and (item / '__init__.py').exists():
            packages.add(item.name)
    return packages

def classify_import(module: str, stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify an import module into categories: 'stdlib', 'third_party', or 'project'.

    Args:
        module: The module name being imported.
        stdlib: Set of standard library module names.
        project_pkgs: Set of top-level project packages.

    Returns:
        The category name.
    """
    root = module.split('.', 1)[0]
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

def process_imports(tree: ast.AST, stdlib: Set[str], project_pkgs: Set[str]) -> Tuple[bool, List[str]]:
    """Process import nodes in the AST and determine if reordering is needed.

    Args:
        tree: AST of the parsed Python file.
        stdlib: Set of standard library module names.
        project_pkgs: Set of top-level project packages.

    Returns:
        A tuple (modified, import_lines) where:
          - modified: whether the import block order needs to change.
          - import_lines: list of normalized import lines for rewriting.
    """
    imports: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    original_lines: List[str] = []

    # Walk through the AST and collect import info
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
            normalized = normalize_import('', modules)
            original_lines.append(normalized)
            imports[classify_import(modules[0], stdlib, project_pkgs)][''].extend(modules)
            logging.debug("Found import: %s", normalized)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            names = [alias.name for alias in node.names]
            normalized = normalize_import(module, names)
            original_lines.append(normalized)
            imports[classify_import(module, stdlib, project_pkgs)][module].extend(names)
            logging.debug("Found import from: %s", normalized)

    if not imports:
        logging.debug("No import statements found.")
        return False, []

    # Build normalized new import lines sorted by category and module
    new_lines: List[str] = []
    for category in ['stdlib', 'third_party', 'project']:
        for module, names in sorted(imports.get(category, {}).items()):
            unique_names = sorted(set(names))
            new_lines.append(normalize_import(module, unique_names))
        if imports.get(category):
            new_lines.append('')  # separate categories

    # Remove trailing blank separators
    while new_lines and new_lines[-1] == '':
        new_lines.pop()

    # Determine if modification is needed by comparing ordered lists
    # Flatten original_lines to exclude duplicates but preserve order
    original_unique: List[str] = []
    seen: Set[str] = set()
    for line in original_lines:
        if line not in seen:
            original_unique.append(line)
            seen.add(line)

    modified = original_unique != new_lines
    if modified:
        logging.debug("Import block needs reordering.")
    else:
        logging.debug("Import block is already correctly ordered.")
    return modified, new_lines

def rewrite_imports(lines: List[str], start: int, end: int, new_imports: List[str]) -> List[str]:
    """Rewrite the import block within lines[start:end] with new_imports.

    Args:
        lines: List of all lines in the file.
        start: Start line index of import block.
        end: End line index of import block.
        new_imports: List of normalized import lines.

    Returns:
        A list of lines representing the file with the import block rewritten.
    """
    return lines[:start] + new_imports + lines[end:]

def find_import_block(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Find the start and end indices of the contiguous block of import statements.

    Args:
        lines: The lines of the file.

    Returns:
        A tuple (start, end) indices of the import block, or None if no import block found.
    """
    start: Optional[int] = None
    end: Optional[int] = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            if start is None:
                start = i
            end = i + 1
        elif start is not None and line.strip():
            break
    return (start, end) if start is not None and end is not None else None

def process_file(file_path: Path, stdlib: Set[str], project_pkgs: Set[str], apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a single Python file, check and fix import ordering.

    Args:
        file_path: Path to the Python file.
        stdlib: Set of standard library module names.
        project_pkgs: Set of top-level project packages.
        apply: If True, apply changes and rewrite the file.

    Returns:
        A tuple (modified, warnings). 'modified' indicates whether the file was updated,
        and 'warnings' contains tuples of (line_number, message) if modifications are needed or errors occur.
    """
    try:
        source = file_path.read_text()
    except Exception as e:
        return False, [(0, f"Could not read file: {e}")]

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, [(e.lineno or 0, f"Syntax error: {e.msg}")]

    modified, new_import_lines = process_imports(tree, stdlib, project_pkgs)
    if not modified:
        return False, []

    lines = source.splitlines()
    block = find_import_block(lines)
    if not block:
        return False, [(0, "Import block could not be located.")]

    start, end = block
    warnings: List[Tuple[int, str]] = [(start + 1, "Imports are not ordered correctly.")]
    if apply:
        new_lines = rewrite_imports(lines, start, end, new_import_lines)
        try:
            file_path.write_text('\n'.join(new_lines) + '\n')
        except Exception as e:
            warnings.append((0, f"Could not write file: {e}"))
            return False, warnings
        return True, warnings
    else:
        return True, warnings

def iter_python_files(root: Path, exclude: Optional[Iterable[str]] = None) -> Iterator[Path]:
    """Yield Python files under the given root directory.

    Args:
        root: The root directory to search for Python files.
        exclude: An optional iterable of directory names to skip (e.g. ['venv', '.git']).

    Yields:
        Paths to Python files relative to the root directory.
    """
    exclude_set = set(exclude) if exclude else set()
    for path in root.rglob('*.py'):
        if any(part in exclude_set for part in path.parts):
            continue
        yield path
