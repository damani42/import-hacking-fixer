#!/usr/bin/env python3
"""Core utilities for import-hacking-fixer.

This module provides functions to classify and normalize import statements,
detect issues with import order, and fix them in Python files. It also exposes
functions to discover project packages and standard library modules.
"""

from __future__ import annotations

import ast
from collections import defaultdict
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union

# Import helper functions from parser and rules modules
from .parser import extract_imports_from_file
from .rules import classify_import as classify_import_rule

def get_stdlib_modules() -> Set[str]:
    """Return a set of top-level standard library module names."""
    stdlib_dir = Path(sys.modules['sys'].__file__).parent
    modules: Set[str] = set()
    for entry in stdlib_dir.iterdir():
        name = entry.name
        if entry.is_file() and name.endswith(".py") and name != "__init__.py":
            modules.add(name[:-3])
        elif entry.is_dir():
            modules.add(name)
    return {mod.split(".")[0] for mod in modules}

def find_project_packages(root: Union[str, Path]) -> Set[str]:
    """Return a set of top-level package names for the given project root."""
    packages: Set[str] = set()
    root_path = Path(root)
    for entry in root_path.iterdir():
        if entry.is_dir() and (entry / "__init__.py").is_file():
            packages.add(entry.name)
    return packages

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
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            classification = classify_import_rule(node)
            if classification == "third_party":
                category = "thirdparty"
            elif classification == "local":
                category = "project"
            else:
                category = classification
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    imports_by_type[category].append(module_name)
                    import_nodes.append((node, module_name, set()))
            else:
                module = node.module or ""
                names = {alias.name for alias in node.names}
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
    original_lines = []
    import_block_start, import_block_end = find_import_block(tree)
    if import_block_start is not None:
        for nd, mod_name, names_set in import_nodes:
            lineno = getattr(nd, "lineno", None)
            if lineno is not None:
                original_lines.append(lineno)
        original_lines = sorted(set(original_lines))
    if new_import_lines and original_lines:
        modified = True
    return modified, [(line, "Import order/style can be improved") for line in original_lines]

def rewrite_imports(lines: List[str], new_import_lines: List[str], start: int, end: int) -> None:
    """Rewrite the import block in lines from start to end."""
    del lines[start:end]
    lines[start:start] = new_import_lines + [""]

def find_import_block(tree: ast.Module) -> Tuple[Optional[int], Optional[int]]:
    """Find the start and end line numbers of the top import block."""
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.append(node.lineno - 1)
        else:
            break
    if not import_lines:
        return None, None
    return import_lines[0], import_lines[-1] + 1

def process_file(file_path: Union[str, Path], stdlib: Set[str], project_pkgs: Set[str], apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a Python file and optionally rewrite imports."""
    path = Path(file_path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, []
    try:
        _ = extract_imports_from_file(str(file_path))
    except SyntaxError:
        pass
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, [(exc.lineno or 0, f"SyntaxError: {exc.msg}")]
    modified, warnings = process_imports(tree, stdlib, project_pkgs)
    if modified and apply:
        start, end = find_import_block(tree)
        if start is not None and end is not None:
            lines = source.splitlines()
            imports_by_type: Dict[str, List[str]] = defaultdict(list)
            import_nodes: List[Tuple[ast.AST, str, Set[str]]] = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    classification = classify_import_rule(node)
                    if classification == "third_party":
                        category = "thirdparty"
                    elif classification == "local":
                        category = "project"
                    else:
                        category = classification
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name
                            imports_by_type[category].append(module_name)
                            import_nodes.append((node, module_name, set()))
                    else:
                        module = node.module or ""
                        names = {alias.name for alias in node.names}
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
                    for nd, mod_name, names_set in import_nodes:
                        if mod_name == module:
                            names |= names_set
                    new_import_lines.append(normalize_import(module, names))
            rewrite_imports(lines, new_import_lines, start, end)
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
