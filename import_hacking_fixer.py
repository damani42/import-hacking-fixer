#!/usr/bin/env python3
"""
import_hacking_fixer.py

Command-line tool to check and fix Python import statements according to the
OpenStack Hacking style guidelines (H301, H303, H304, H306).

Usage:
    python import_hacking_fixer.py PATH [--apply] [--project-packages PKG1,PKG2]
"""

import argparse
import ast
import os
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Set, Tuple


def get_stdlib_modules() -> Set[str]:
    """Return a set of standard library top-level modules."""
    stdlib: Set[str] = set()
    if hasattr(sys, "stdlib_module_names"):
        stdlib.update(sys.stdlib_module_names)
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
    """Identify top-level packages in the given project root by presence of __init__.py."""
    packages: Set[str] = set()
    for entry in os.listdir(root):
        path = os.path.join(root, entry)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "__init__.py")):
            packages.add(entry)
    return packages


def classify_import(module: str, stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify module name into 'stdlib', 'project' or 'thirdparty'."""
    top = module.split(".")[0]
    if top in stdlib:
        return "stdlib"
    if top in project_pkgs:
        return "project"
    return "thirdparty"


def normalize_import(name: str, alias: str = None) -> str:
    return name if alias is None else f"{name} as {alias}"


def process_imports(nodes: Iterable[ast.AST], stdlib: Set[str], project_pkgs: Set[str]) -> Tuple[Dict[str, List[str]], List[Tuple[int, str]]]:
    """Process import nodes, grouping and sorting them, and collect warnings.

    Records H301 for multiple imports on a single line, H303 for wildcard imports and H304 for relative imports.
    Returns a dictionary mapping group names to lists of import statements and a list of warnings.
    """
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
            if node.module == '__future__':
                continue
            if node.level and node.level > 0:
                warnings.append((node.lineno, f"H304: relative import detected: 'from {'.' * node.level}{node.module or ''} import ...'"))
                continue
            base_mod = node.module or ''
            if len(node.names) > 1:
                warnings.append((node.lineno, f"H301: multiple names imported from '{base_mod}' on one line"))
            for alias in node.names:
                if alias.name == '*':
                    warnings.append((node.lineno, f"H303: wildcard import detected from '{base_mod}'"))
                    continue
                full_name = f"{base_mod}.{alias.name}" if base_mod else alias.name
                key = classify_import(base_mod, stdlib, project_pkgs)
                groups[key].append(normalize_import(full_name, alias.asname))
    for key in groups:
        groups[key] = sorted(groups[key], key=lambda x: x.lower())
    return groups, warnings


def rewrite_imports(original_lines: List[str], groups: Dict[str, List[str]]) -> List[str]:
    """Compose new import block from grouped imports. Always ends with a blank line."""
    new_import_lines: List[str] = []
    order = ['stdlib', 'thirdparty', 'project']
    for group in order:
        if groups.get(group):
            for imp in groups[group]:
                if '.' in imp:
                    parts = imp.split(' as ')
                    name_part = parts[0]
                    alias_part = parts[1] if len(parts) == 2 else None
                    pkg, sub = name_part.rsplit('.', 1)
                    if alias_part:
                        new_import_lines.append(f"from {pkg} import {sub} as {alias_part}\n")
                    else:
                        new_import_lines.append(f"from {pkg} import {sub}\n")
                else:
                    new_import_lines.append(f"import {imp}\n")
            new_import_lines.append("\n")
    return new_import_lines


def find_import_block(lines: List[str]) -> Tuple[int, int]:
    """Find the start and end line indices (inclusive) of the import block."""
    start = None
    end = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            if start is None:
                start = idx
            end = idx
        elif start is not None and stripped == '':
            end = idx
        elif start is not None:
            break
    if start is None:
        return (-1, -1)
    return (start, end)


def process_file(path: str, stdlib: Set[str], project_pkgs: Set[str], apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a single Python file. Returns (modified, warnings). If apply is True, rewrite the file."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    tree = ast.parse(''.join(lines), filename=path)
    import_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    groups, warnings = process_imports(import_nodes, stdlib, project_pkgs)
    if not import_nodes:
        return False, warnings
    start, end = find_import_block(lines)
    if start == -1:
        return False, warnings
    new_imports = rewrite_imports(lines[start:end+1], groups)
    new_content = ''.join(new_imports) + ''.join(lines[end+1:])
    original_content = ''.join(lines)
    modified = new_content != original_content
    if modified and apply:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    return modified, warnings


def iter_python_files(path: str) -> Iterable[str]:
    """Yield Python file paths under the given path (file or directory)."""
    if os.path.isdir(path):
        for root, _, filenames in os.walk(path):
            for fn in filenames:
                if fn.endswith('.py'):
                    yield os.path.join(root, fn)
    else:
        if path.endswith('.py'):
            yield path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check and fix Python imports (OpenStack style).")
    parser.add_argument("path", help="file or directory to process")
    parser.add_argument("--apply", action="store_true", help="rewrite files instead of only reporting")
    parser.add_argument("--project-packages", default="", help="comma-separated list of top-level project packages")
    args = parser.parse_args()
    stdlib = get_stdlib_modules()
    project_pkgs = set(filter(None, (p.strip() for p in args.project_packages.split(','))))
    if not project_pkgs and os.path.isdir(args.path):
        project_pkgs = find_project_packages(args.path)
    for file_path in iter_python_files(args.path):
        modified, warnings = process_file(file_path, stdlib, project_pkgs, apply=args.apply)
        for lineno, msg in warnings:
            print(f"[{file_path}] line {lineno}: {msg}")
        if modified:
            if args.apply:
                print(f"[{file_path}] file updated.")
            else:
                print(f"[{file_path}] imports would be modified.")


if __name__ == "__main__":
    main()
