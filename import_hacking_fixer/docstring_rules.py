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

    # Process docstrings in reverse order to avoid index shifting issues
    docstring_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc and "\n" in doc:
                doc_lines = doc.splitlines()
                # Only apply if the second line (index 1) is not empty
                if len(doc_lines) > 1 and doc_lines[1].strip() != "":
                    # Find the actual docstring node in the AST
                    docstring_node = None
                    if hasattr(node, "body") and node.body:
                        for stmt in node.body:
                            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                                docstring_node = stmt
                                break
                    
                    if docstring_node:
                        docstring_nodes.append((docstring_node, doc_lines))

    # Process docstrings in reverse order (bottom to top) to avoid index shifting
    for docstring_node, doc_lines in reversed(docstring_nodes):
        # Get the original indentation from the source
        docstring_line_idx = docstring_node.lineno - 1
        original_line = lines[docstring_line_idx]
        
        # Find the indentation of the docstring opening
        indent_match = len(original_line) - len(original_line.lstrip())
        indent = original_line[:indent_match]
        
        # Determine lineno for warning
        lineno = docstring_node.lineno
        warnings.append((lineno, "H405: multi-line docstring summary not separated with an empty line"))
        
        # Build new docstring lines with proper indentation
        summary = doc_lines[0]
        rest = doc_lines[1:]
        
        # Find the end line of the docstring
        end_line_idx = docstring_node.end_lineno - 1  # type: ignore
        
        # Create new docstring lines - single docstring with blank line inside
        new_doc_lines = []
        new_doc_lines.append(indent + '"""' + summary)
        new_doc_lines.append(indent)  # Empty line after summary (no closing quotes!)
        
        # Add the rest of the docstring - preserve original indentation
        for line in rest:
            # Strip leading whitespace from the original line and re-add base indent
            new_doc_lines.append(indent + line.lstrip())
        
        new_doc_lines.append(indent + '"""')
        
        # Replace the docstring lines
        lines[docstring_line_idx:end_line_idx + 1] = new_doc_lines
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
