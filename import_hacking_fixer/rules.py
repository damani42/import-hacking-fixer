"""Rules module for import-hacking-fixer.

This module defines rules for validating import statements according to OpenStack hacking guidelines.

Currently includes a basic classification of imports into standard library, third-party, and local.
"""

import ast
import sys
import sysconfig
from pathlib import Path
import pkgutil
import importlib.util
from typing import List, Dict


def _get_stdlib_modules() -> set:
    """Return a set of module names that are part of the Python standard library."""
    stdlib_path = Path(sysconfig.get_paths()['stdlib'])
    modules = set(sys.builtin_module_names)
    # include pure python modules in stdlib directory
    for p in stdlib_path.glob('*.py'):
        modules.add(p.stem)
    # include package directories with __init__.py
    for d in stdlib_path.iterdir():
        if d.is_dir() and (d / '__init__.py').exists():
            modules.add(d.name)
    return modules


# Precompute stdlib modules at import time
_STDLIB_MODULES = _get_stdlib_modules()


def classify_import(node: ast.stmt) -> str:
    """Classify an import statement as 'stdlib', 'third_party', or 'local'.

    Args:
        node: An AST Import or ImportFrom node.

    Returns:
        A string representing the classification of the import.
    """
    # Determine module name for import statement
    if isinstance(node, ast.Import):
        name = node.names[0].name.split('.')[0]
    elif isinstance(node, ast.ImportFrom):
        # Relative import (level > 0) or missing module is considered local
        if node.level and node.level > 0:
            return 'local'
        if node.module is None:
            return 'local'
        name = node.module.split('.')[0]
    else:
        raise ValueError("Unsupported node type for import classification")

    # Standard library modules (including built-ins)
    if name in _STDLIB_MODULES:
        return 'stdlib'

    # Determine if module is local or third party
    spec = importlib.util.find_spec(name)
    if spec is None:
        # If no spec, treat as local
        return 'local'
    origin = spec.origin
    if origin is None:
        # No origin found; treat built-in as stdlib (should be covered above)
        return 'stdlib'

    # Determine if the module's origin is within the current working directory
    try:
        project_root = Path.cwd().resolve()
        origin_path = Path(origin).resolve()
        if str(origin_path).startswith(str(project_root)):
            return 'local'
    except Exception:
        # Fall back to third party
        pass
    return 'third_party'


def split_imports(imports: List[ast.stmt]) -> dict:
    """Split a list of import statements into categories.

    Args:
        imports: A list of AST Import or ImportFrom nodes.

    Returns:
        A dictionary with keys 'stdlib', 'third_party', and 'local' mapping to lists of imports.
    """
    grouped = {'stdlib': [], 'third_party': [], 'local': []}
    for node in imports:
        category = classify_import(node)
        grouped[category].append(node)
    return grouped
