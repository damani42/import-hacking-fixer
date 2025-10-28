"""Parser module for import-hacking-fixer.

This module provides functions to extract import statements from Python files.
"""

from typing import List
import ast






def extract_imports_from_file(file_path: str) -> List[ast.stmt]:
    """Parse a Python file and return a list of import statements (AST nodes).

    Args:
        file_path: Path to the Python source file.

    Returns:
        A list of ast.Import or ast.ImportFrom nodes representing the import
        statements found in the file.

    Raises:
        SyntaxError: If the Python file contains invalid syntax.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Parse the source code into an AST
    tree = ast.parse(source, filename=file_path)

    # Walk the AST and collect all import statements
    imports: List[ast.stmt] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)

    return imports
