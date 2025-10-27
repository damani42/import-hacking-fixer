#!/usr/bin/env python3
"""Core utilities for import-hacking-fixer.

This module provides functions to classify and normalize import statements, detect issues
with import order, and fix them in Python files. It also exposes functions to discover
project packages and standard library modules.
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
    and returns the names of .py files or packages (directories containing an
    ``__init__.py`` file). Only top-level modules are considered.

    Returns:
        A set of module names representing top-level standard library modules.
    """
    stdlib: Set[str] = set()
    # built-in module names
    for name in sys.builtin_module_names:
        stdlib.add(name)
    # inspect the library directory (the first entry of sys.path is typically the stdlib)
    libdir = Path(sys.path[0])
    for entry in libdir.iterdir():
        if entry.name.startswith("_"):
            continue
        if entry.is_file() and entry.suffix == ".py":
            stdlib.add(entry.stem)
        elif entry.is_dir() and (entry / "__init__.py").exists():
            stdlib.add(entry.name)
    return stdlib


def find_project_packages(root: Path) -> Set[str]:
    """Return a set of top-level package names for a given project root.

    A 'project package' is a directory under the root that contains an
    ``__init__.py`` file. The names returned are the directory names.

    Args:
        root: Path to the project root.

    Returns:
        A set of package names found at top-level.
    """
    packages: Set[str] = set()
    root_path = Path(root)
    for path in root_path.iterdir():
        if path.is_dir() and (path / "__init__.py").exists():
            packages.add(path.name)
    return packages


def classify_import(module: str, stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify an import according to stdlib, third-party or project.

    Args:
        module: The module name from an import statement.
        stdlib: Set of standard library module names.
        project_pkgs: Set of project package names.

    Returns:
        The category: 'stdlib', 'thirdparty', or 'project'.
    """
    root = module.split(".")[0]
    if root in project_pkgs:
        return "project"
    if root in stdlib:
        return "stdlib"
    return "thirdparty"


def normalize_import(node: ast.AST) -> str:
    """Return a normalized string representation of an import node.

    The normalized form is used to compare and sort imports. Import statements are
    collapsed to a single line. ``import a as b`` and ``from x import y as z`` are
    preserved.

    Args:
        node: The :class:`ast.Import` or :class:`ast.ImportFrom` node.

    Returns:
        A normalized string of the import statement.
    """
    if isinstance(node, ast.Import):
        parts: List[str] = []
        for alias in node.names:
            if alias.asname:
                parts.append(f"{alias.name} as {alias.asname}")
            else:
                parts.append(alias.name)
        return f"import {', '.join(parts)}"
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        names: List[str] = []
        for alias in node.names:
            if alias.asname:
                names.append(f"{alias.name} as {alias.asname}")
            else:
                names.append(alias.name)
        level_dots = "." * node.level
        return f"from {level_dots}{module} import {', '.join(names)}"
    raise ValueError("Unsupported node type for normalization")


def process_imports(source: str, stdlib: Set[str], project_pkgs: Set[str]) -> Tuple[bool, List[Tuple[int, str]], List[str]]:
    """Analyze and reorder import statements in the given source.

    Parses the source into an AST, collects import statements, classifies and sorts them,
    and returns whether the import block would be modified along with any warnings and
    the new import lines.

    Args:
        source: The Python source code to analyze.
        stdlib: Set of standard library module names.
        project_pkgs: Set of project package names.

    Returns:
        A tuple ``(modified, warnings, new_import_lines)`` where:

        * ``modified`` (bool): True if the import block needs modification.
        * ``warnings`` (list): Each warning is a tuple ``(line number, message)``.
        * ``new_import_lines`` (list): Sorted import lines that should replace the current block.
    """
    tree = ast.parse(source)
    warnings: List[Tuple[int, str]] = []
    imports: List[ast.AST] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
            logging.debug("Found import: %s", normalize_import(node))

    if not imports:
        return False, warnings, []

    # Capture the normalized original import lines (preserve duplicates order)
    original_lines: List[str] = [normalize_import(node) for node in imports]

    # Build categories
    categories: Dict[str, List[str]] = defaultdict(list)
    for node in imports:
        if isinstance(node, ast.Import):
            module_name = node.names[0].name
        else:
            module_name = node.module or ""
        category = classify_import(module_name, stdlib, project_pkgs)
        categories[category].append(normalize_import(node))

    # Sort imports within each category lexicographically (case-insensitive)
    new_import_lines: List[str] = []
    for category_name in ("stdlib", "thirdparty", "project"):
        lines = categories.get(category_name, [])
        if lines:
            sorted_lines = sorted(lines, key=lambda s: s.lower())
            new_import_lines.extend(sorted_lines)
            new_import_lines.append("")  # separator
    if new_import_lines and new_import_lines[-1] == "":
        new_import_lines.pop()

    # Determine if modifications are needed by comparing sorted unique sets
    original_unique_sorted = sorted(set(original_lines), key=lambda s: s.lower())
    new_unique_sorted = sorted(set(new_import_lines), key=lambda s: s.lower())
    modified = original_unique_sorted != new_unique_sorted

    # Add warnings for wildcard imports
    for node in imports:
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            warnings.append((node.lineno, "Avoid wildcard imports"))

    return modified, warnings, new_import_lines


def rewrite_imports(lines: List[str], import_block: Tuple[int, int], new_imports: List[str]) -> None:
    """Rewrite the lines list in-place by replacing the import block with new imports.

    Args:
        lines: The list of source lines to modify.
        import_block: A tuple ``(start, end)`` representing the inclusive line numbers of the import block.
        new_imports: A list of normalized import lines to insert.
    """
    start, end = import_block
    # Convert to 0-based indices and replace
    lines[start - 1 : end] = [ln + "\n" if ln else "\n" for ln in new_imports]


def find_import_block(source_lines: List[str]) -> Optional[Tuple[int, int]]:
    """Find the contiguous block of import statements at the top of the file.

    Args:
        source_lines: The list of lines from the source file.

    Returns:
        A tuple ``(start_line, end_line)`` if an import block is found, or ``None`` if no imports are present.
    """
    start: Optional[int] = None
    end: Optional[int] = None
    for idx, line in enumerate(source_lines, start=1):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            if start is None:
                start = idx
            end = idx
        else:
            if start is not None:
                break
    if start is not None and end is not None:
        return start, end
    return None


def process_file(file_path: Path, stdlib: Set[str], project_pkgs: Set[str], *, apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a Python file: detect and optionally fix import ordering.

    Args:
        file_path: Path to the file to process.
        stdlib: Set of standard library module names.
        project_pkgs: Set of project package names.
        apply: If True, rewrite the file with sorted imports; otherwise just report.

    Returns:
        A tuple ``(modified, warnings)``. ``modified`` is True if the file was changed or should be changed,
        ``warnings`` is a list of ``(line, message)`` pairs.
    """
    text = file_path.read_text(encoding="utf-8")
    modified, warnings, new_import_lines = process_imports(text, stdlib, project_pkgs)
    if not modified:
        return False, warnings
    if apply:
        lines = text.splitlines(keepends=True)
        block = find_import_block(lines)
        if block:
            rewrite_imports(lines, block, new_import_lines)
            file_path.write_text("".join(lines), encoding="utf-8")
    return True, warnings


def iter_python_files(root: Path, *, exclude: Optional[Iterable[str]] = None) -> Iterator[Path]:
    """Yield Python file paths under the given root.

    Performs a recursive search for ``*.py`` files under the root directory
    and yields :class:`pathlib.Path` objects. Optionally, directories whose names appear
    in the ``exclude`` iterable will be skipped.

    Args:
        root: The directory to search.
        exclude: Iterable of directory names to exclude from recursion, e.g. {"venv", ".git"}.

    Yields:
        Paths to Python files.
    """
    root_path = Path(root)
    exclude_set: Set[str] = set(exclude) if exclude else set()
    for path in root_path.rglob("*.py"):
        if any(part in exclude_set for part in path.parts):
            continue
        yield path
