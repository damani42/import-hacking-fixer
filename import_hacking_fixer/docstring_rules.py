import ast
from typing import List, Tuple


def process_docstrings(source: str) -> Tuple[bool, List[Tuple[int, str]], str]:
    """
    Process docstrings in the given source code and fix rule H405.

    Returns a tuple (modified, warnings, new_source).
    If a docstring is multi-line and the summary line is not followed by a blank line,
    this function will insert a blank line and return modified=True.
    """
    tree = ast.parse(source)
    lines = source.splitlines()
    warnings: List[Tuple[int, str]] = []
    modified = False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc and "\n" in doc:
                doc_lines = doc.splitlines()
                # Only apply if the second line (index 1) is not empty
                if len(doc_lines) > 1 and doc_lines[1].strip() != "":
                    # Determine lineno for warning: use start line of docstring
                    lineno = node.body[0].lineno if hasattr(node, "body") and node.body else node.lineno
                    warnings.append((lineno, "H405: multi-line docstring summary not separated with an empty line"))
                    indent = " " * node.col_offset
                    summary = doc_lines[0]
                    rest = doc_lines[1:]
                    new_doc_lines = [indent + '"""', indent + summary, indent + ""]
                    for l in rest:
                        new_doc_lines.append(indent + l)
                    new_doc_lines.append(indent + '"""')
                    # Replace lines in original source
                    if hasattr(node, "body") and node.body:
                        start = node.body[0].lineno - 1
                        end = node.body[0].end_lineno - 1  # type: ignore
                    else:
                        start = node.lineno - 1
                        end = node.end_lineno - 1  # type: ignore
                    lines[start:end + 1] = new_doc_lines
                    modified = True

    new_source = "\n".join(lines)
    return modified, warnings, new_source


def process_file(file_path: str, apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """
    Process a Python file to fix H405 docstring issues.

    If apply is True and any modifications are made, the file will be rewritten in place.
    Returns a tuple of (modified, warnings).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    modified, warnings, new_source = process_docstrings(source)
    if modified and apply:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_source)
    return modified, warnings
