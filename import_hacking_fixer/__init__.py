"""Top-level package for import-hacking-fixer.

This package exposes the core API for checking and fixing Python import statements.
"""

from import_hacking_fixer.core import (
    get_stdlib_modules,
    find_project_packages,
    classify_import,
    normalize_import,
    process_imports,
    rewrite_imports,
    find_import_block,
    process_file,
    iter_python_files,
)

__all__ = [
    "get_stdlib_modules",
    "find_project_packages",
    "classify_import",
    "normalize_import",
    "process_imports",
    "rewrite_imports",
    "find_import_block",
    "process_file",
    "iter_python_files",
]
