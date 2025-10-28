"""Top-level package for import-hacking-fixer.

This package exposes the core API for checking and fixing Python import statements.
"""

from import_hacking_fixer.core import classify_import
from import_hacking_fixer.core import find_import_block
from import_hacking_fixer.core import find_project_packages
from import_hacking_fixer.core import get_stdlib_modules
from import_hacking_fixer.core import iter_python_files
from import_hacking_fixer.core import normalize_import
from import_hacking_fixer.core import process_file
from import_hacking_fixer.core import process_imports
from import_hacking_fixer.core import rewrite_imports


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
