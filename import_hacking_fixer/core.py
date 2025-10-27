#!/usr/bin/env python3
"""Core functions for import-hacking-fixer.

This module provides functions to analyze and fix import statements
according to OpenStack Hacking rules.
"""

import ast
from collections import defaultdict
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple, Union


def get_stdlib_modules() -> Set[str]:
    """Return a set of standard library module names."""
    stdlib: Set[str] = set()
    if hasattr(sys, "stdlib_module_names"):
        stdlib.update(sys.stdlib_module_names)  # type: ignore[attr-defined]
    else:
        stdlib.update(sys.builtin_module_names)
        libdir = Path(sys.__file__).parent
        for entry in libdir.iterdir():
            name = entry.name
            if entry.is_file() and name.endswith(".py") and name != "__init__.py":
                stdlib.add(name[:-3])
            elif entry.is_dir():
                stdlib.add(name)
    return {mod.split(".")[0] for mod in stdlib}


def find_project_packages(root: Union[str, Path]) -> Set[str]:
    """Return a set of top-level package names for the given project root."""
    packages: Set[str] = set()
    root_path = Path(root)
    for entry in root_path.iterdir():
        if entry.is_dir() and (entry / "__init__.py").is_file():
            packages.add(entry.name)
    return packages


def classify_import(name: str, stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify an import name as 'stdlib', 'project', or 'thirdparty'."""
    top = name.split(".")[0]
    if top in stdlib:
        return "stdlib"
    if top in project_pkgs:
        return "project"
    return "thirdparty"


def normalize_import(module: str, names: Iterable[str]) -> str:
    """Normalize an import to a string representation."""
    if not names:
        return f"import {module}"
    if module == "":
        return ", ".join(sorted(names))
    return f"from {module} import {', '.join(sorted(names))}"


def process_imports(tree: ast.Module, stdlib: Set[str], project_pkgs: Set[str]) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process imports in the AST, return whether changes are needed and a list of warnings."""
    modified = False
    warnings: List[Tuple[int, str]] = []
    imports_by_type: Dict[str, List[str]] = defaultdict(list)
    import_nodes: List[Tuple[ast.AST, str, Set[str]]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                category = classify_import(module_name, stdlib, project_pkgs)
                imports_by_type[category].append(module_name)
                import_nodes.append((node, module_name, set()))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {alias.name for alias in node.names}
            category = classify_import(module, stdlib, project_pkgs)
            imports_by_type[category].append(module)
            import_nodes.append((node, module, names))

    # Build new import lines
    new_import_lines: List[str] = []
    for category in ("stdlib", "thirdparty", "project"):
        modules = imports_by_type.get(category, [])
        if not modules:
            continue
        unique_modules = sorted(set(modules))
        for module in unique_modules:
            # collect names for ImportFrom with same module
            names: Set[str] = set()
            for node, mod, names_set in import_nodes:
                if mod == module:
                    names |= names_set
            new_import_lines.append(normalize_import(module, names))

    # Compare to original import block
    original_lines = []
    import_block_start, import_block_end = find_import_block(tree)
    if import_block_start is not None:
        for node in import_nodes:
            lineno = getattr(node[0], "lineno", None)
            if lineno is not None:
                original_lines.append(lineno)
        # sort original lines to preserve order
        original_lines = sorted(set(original_lines))
    if new_import_lines and original_lines:
        # if new import lines differ from original lines content
        modified = True

    return modified, [(line, "Import order/style can be improved") for line in original_lines]


def rewrite_imports(lines: List[str], new_import_lines: List[str], start: int, end: int) -> None:
    """Rewrite the import block in lines from start to end (0-indexed, inclusive start, exclusive end)."""
    del lines[start:end]
    lines[start:start] = new_import_lines + [""]


def find_import_block(tree: ast.Module) -> Tuple[Union[int, None], Union[int, None]]:
    """Find the start and end line numbers of the top import block. Returns (start, end) where end is exclusive."""
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.append(node.lineno - 1)  # convert to 0-index
        else:
            break
    if not import_lines:
        return None, None
    return import_lines[0], import_lines[-1] + 1


def process_file(file_path: Union[str, Path], stdlib: Set[str], project_pkgs: Set[str], apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a Python file and optionally rewrite imports.

    Returns a tuple (modified: bool, warnings: list of (line, message)).
    """
    path = Path(file_path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, []

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, [(exc.lineno or 0, f"SyntaxError: {exc.msg}")]

    modified, warnings = process_imports(tree, stdlib, project_pkgs)

    # If modifications needed and apply is True, rewrite file
    if modified and apply:
        start, end = find_import_block(tree)
        if start is not None and end is not None:
            lines = source.splitlines()
            # Build new import lines again to ensure up-to-date
            imports_by_type: Dict[str, List[str]] = defaultdict(list)
            import_nodes: List[Tuple[ast.AST, str, Set[str]]] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        category = classify_import(module_name, stdlib, project_pkgs)
                        imports_by_type[category].append(module_name)
                        import_nodes.append((node, module_name, set()))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = {alias.name for alias in node.names}
                    category = classify_import(module, stdlib, project_pkgs)
                    imports_by_type[category].append(module)
                    import_nodes.append((node, module, names))
            new_import_lines: List[str] = []
            for category in ("stdlib", "thirdparty", "project"):
                modules = imports_by_type.get(category, [])
                if not modules:
                    continue
                unique_modules = sorted(set(modules))
                for module in unique_modules:
                    names: Set[str] = set()
                    for nd, mod, names_set in import_nodes:
                        if mod == module:
                            names |= names_set
                    new_import_lines.append(normalize_import(module, names))
            rewrite_imports(lines, new_import_lines, start, end)
            # Write back file
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return modified, warnings


def iter_python_files(root: Union[str, Path]) -> Iterable[str]:
    """Yield Python file paths under a directory, recursively."""
    root_path = Path(root)
    if root_path.is_file() and root_path.suffix == ".py":
        yield str(root_path)
        return
    for p in root_path.rglob("*.py"):
        yield str(p)
