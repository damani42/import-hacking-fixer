"""Rules module for import-hacking-fixer.

This module defines rules for validating import statements according to OpenStack hacking guidelines.

Currently includes a basic classification of imports into standard library, third-party, and local.
"""

import ast
import sys
import pkgutil
from typing import List


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
        # Relative import (level > 0) is considered local
        if node.level and node.level > 0:
            return "local"
        name = (node.module or "").split('.')[0]
    else:
        return "local"

    # Check if it's a built-in module (standard library)
    if name in sys.builtin_module_names:
        return "stdlib"
    try:
        # If loader found, assume third-party or stdlib. A None loader implies it may not be importable.
        loader = pkgutil.find_loader(name)
        if loader is None:
            return "local"
    except Exception:
        return "local"

    # For now treat anything not built-in as third_party
    return "third_party"
