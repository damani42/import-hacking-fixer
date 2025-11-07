#!/usr/bin/env python3
"""Core utilities for import-hacking-fixer. This module 
provides functions to classify and normalize import statements, detect issues 
with import order, and fix them in Python files. It also exposes functions to 
discover project packages and standard library modules.
"""
from __future__ import annotations
import ast
import subprocess
from collections import defaultdict
import logging
from pathlib import Path
import sys
import sysconfig
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from .docstring_rules import process_docstrings
from import_hacking_fixer.style_rules import read_line_length_config, check_line_length

LOG = logging.getLogger(__name__)


def get_stdlib_modules() -> Set[str]:
    """Return a set of top-level standard library module names."""
    # Use sysconfig to get the standard library directory and include built-in modules
    stdlib_dir = Path(sysconfig.get_paths()['stdlib'])
    modules: Set[str] = set(sys.builtin_module_names)
    for entry in stdlib_dir.iterdir():
        name = entry.stem
        if entry.is_file() and entry.suffix == '.py':
            modules.add(name)
        elif entry.is_dir() and (entry / '__init__.py').exists():
            modules.add(name)
    return modules

def find_project_packages(root: str) -> Set[str]:
    """Return a set of top-level package names for the given project root."""
    packages: Set[str] = set()
    root_path = Path(root)
    for item in root_path.iterdir():
        if item.is_dir() and (item / '__init__.py').exists():
            packages.add(item.name)
    return packages

def classify_import(module: str, stdlib: Set[str], project_pkgs: Set[str]) -> str:
    """Classify an import module into categories: 'stdlib', 'third_party', or 'project'."""
    root = module.split('.', 1)[0] if module else ''
    if root in stdlib:
        return 'stdlib'
    if root in project_pkgs:
        return 'project'
    return 'third_party'

def normalize_import(module: str, names: List[str]) -> str:
    """Normalize an import statement to a single-line representation."""
    if module:
        return f"from {module} import {', '.join(names)}"
    else:
        return f"import {', '.join(names)}"

def import_normalize(line: str) -> str:
    """Convert 'from x import y' to 'import x.y' for alphabetical comparison.
    
    This matches hacking.core.import_normalize behavior.
    """
    split_line = line.split()
    if ("import" in line and line.startswith("from ") and "," not in line and
            split_line[2] == "import" and split_line[3] != "*" and
            split_line[1] != "__future__" and
            (len(split_line) == 4 or
             (len(split_line) == 6 and split_line[4] == "as"))):
        return "import %s.%s" % (split_line[1], split_line[3])
    else:
        return line

def process_imports(tree: ast.AST, stdlib: Set[str], project_pkgs: Set[str]) -> Tuple[bool, List[str], List[Tuple[int, str]]]:
    """Process import nodes in the AST and build a sorted list of normalized imports
    and warnings. Returns a tuple (modified, new_import_lines, warnings).
    """
    imports_list: List[Tuple[str, str, str, str]] = []
    warnings: List[Tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # detect multiple names (H301)
            if len(node.names) > 1:
                warnings.append((node.lineno, "H301: one import per line"))
            for alias in node.names:
                name = alias.name
                # Special handling for common stdlib submodules that should stay as import
                special_cases = {'importlib.util', 'importlib.metadata', 'typing.Dict', 'typing.List', 
                               'typing.Set', 'typing.Tuple', 'typing.Optional', 'typing.Iterable', 
                               'typing.Iterator', 'collections.defaultdict', 'pathlib.Path'}
                
                if name in special_cases:
                    # Keep as import statement for special cases
                    category = classify_import(name.split('.')[0], stdlib, project_pkgs)
                    imports_list.append((category, '', name, "import"))
                elif '.' in name:
                    root, rest = name.split('.', 1)
                    # H302: import each attribute from module directly
                    if root in stdlib or root in project_pkgs:
                        category = classify_import(root, stdlib, project_pkgs)
                        imports_list.append((category, root, rest, "from"))
                        warnings.append((node.lineno, f"H302: import each object from '{root}' separately"))
                        continue
                # normal import
                category = classify_import(name.split('.')[0], stdlib, project_pkgs)
                imports_list.append((category, '', name, "import"))
        elif isinstance(node, ast.ImportFrom):
            # relative import detection (H304)
            if getattr(node, 'level', 0):
                rel_prefix = '.' * node.level
                modname = node.module or ''
                warnings.append((node.lineno, f"H304: No relative imports. '{rel_prefix + modname}' is a relative import"))
                continue
            # wildcard detection (H303)
            if any(alias.name == '*' for alias in node.names):
                warnings.append((node.lineno, "H303: No wildcard (*) import."))
                continue
            # multiple names detection (H301 / H302)
            if len(node.names) > 1:
                warnings.append((node.lineno, "H301: one import per line"))
                warnings.append((node.lineno, "H302: import each object on its own line"))
            module = node.module or ''
            for alias in node.names:
                name = alias.name
                category = classify_import(module, stdlib, project_pkgs)
                imports_list.append((category, module, name, "from"))

    LOG.debug(f"Found {len(imports_list)} imports and {len(warnings)} warnings")
    
    if not imports_list:
        LOG.debug("No import statements found.")
        return False, [], warnings

    # Special handling for __future__ imports - they must come first
    future_imports = []
    other_imports = []
    
    for item in imports_list:
        category, module, name, import_type = item
        if module == '__future__':
            future_imports.append(item)
        else:
            other_imports.append(item)
    
    category_order = {'stdlib': 0, 'third_party': 1, 'project': 2}
    # sort by category, then alphabetically (like hacking does)
    sorted_other = sorted(
        other_imports,
        key=lambda x: (
            category_order[x[0]],
            # Use hacking-style normalization for alphabetical sorting
            import_normalize(normalize_import(x[1], [x[2]])).lower(),
        ),
    )
    
    # Combine future imports first, then others
    sorted_list = future_imports + sorted_other

    new_lines: List[str] = []
    seen_keys: Set[Tuple[str, str, str, str]] = set()
    current_category: Optional[str] = None
    
    for category, module, name, import_type in sorted_list:
        key = (category, module, name, import_type)
        if key in seen_keys:
            continue
        if current_category is None:
            current_category = category
        elif category != current_category:
            # Add blank line between different categories (OpenStack style)
            new_lines.append('')
            current_category = category
        
        # build normalized import line
        if import_type == "from":
            # from import
            new_lines.append(normalize_import(module, [name]))
        else:
            new_lines.append(normalize_import('', [name]))
        seen_keys.add(key)
    
    # Add final blank line after all imports
    new_lines.append('')
    modified = True
    return modified, new_lines, warnings

def rewrite_imports(lines: List[str], start: int, end: int, new_imports: List[str]) -> List[str]:
    """Rewrite the import block within lines[start:end] with new_imports."""
    return lines[:start] + new_imports + lines[end:]

def find_import_block(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Find the start and end indices of the contiguous block of import statements."""
    start: Optional[int] = None
    end: Optional[int] = None
    in_import_block = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Check if this is an import line
        if stripped.startswith('import ') or stripped.startswith('from '):
            if start is None:
                start = i
            end = i + 1
            in_import_block = True
        elif stripped == '':
            # Empty line - continue if we're in an import block
            if in_import_block:
                continue
        elif in_import_block:
            # Non-empty, non-import line - end of import block
            break
    
    return (start, end) if start is not None and end is not None else None




def process_file(file_path: str, stdlib: Set[str], project_pkgs: Set[str], apply: bool = False) -> Tuple[bool, List[Tuple[int, str]]]:
    """Process a single Python file, check and fix import ordering and hacking rules.
    Returns (modified, warnings).
    """
    path_obj = Path(file_path)

    try:
        source = path_obj.read_text()
    except Exception as e:
        return False, [(0, f"Could not read file: {e}")]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, [(e.lineno or 0, f"Syntax error: {e.msg}")]
    
    # Process imports
    modified, new_import_lines, import_warnings = process_imports(tree, stdlib, project_pkgs)
    
    # Process docstrings (H405)
    docstring_modified, docstring_warnings, new_source = process_docstrings(source)
    
    # Combine warnings
    all_warnings = import_warnings + docstring_warnings
    
    # Check if any modifications are needed
    if not modified and not docstring_modified and not all_warnings:
        return False, []

    lines = source.splitlines()
    block = find_import_block(lines)
    warnings: List[Tuple[int, str]] = all_warnings.copy()

    # Check line length
    max_length = read_line_length_config(str(Path(file_path).parent))
    length_warnings = check_line_length(file_path, max_length)
    all_warnings.extend(length_warnings)

    if apply:
        # Apply fixes
        if docstring_modified:
            # If docstrings were modified, use the new source from docstring processing
            new_lines = new_source.splitlines()
            if block and modified:
                # Still need to apply import fixes to the docstring-modified source
                start, end = block
                new_lines = rewrite_imports(new_lines, start, end, new_import_lines)
        elif block and modified:
            # Only import fixes needed
            start, end = block
            new_lines = rewrite_imports(lines, start, end, new_import_lines)
        else:
            new_lines = lines.copy()
        
        try:
            path_obj.write_text('\n'.join(new_lines) + '\n')
        except Exception as e:
            warnings.append((0, f"Could not write file: {e}"))
            return False, warnings
        return True, warnings
    else:
        if modified or docstring_modified:
            if block and modified:
                warnings.append((block[0] + 1, "Import order/style is incorrect."))
            if docstring_modified:
                warnings.append((0, "Docstring formatting issues detected."))
        return True, warnings

def iter_python_files(root: str, ignore: Optional[Iterable[str]] = None) -> Iterator[Path]:
    """Yield Python files under the given root directory, excluding specified patterns."""
    ignore_set = set(ignore or [])
    root_path = Path(root)
    for path in root_path.rglob('*.py'):
        if any(str(path).startswith(str(root_path / pattern)) for pattern in ignore_set):
            continue
        yield path


def run_code_formatter(target_path: str, formatter: str):
    """
    Run external code formatters after fixing imports.

    Args:
        target_path: Path or directory to run formatters on.
        formatter: One of 'black', 'flake8', or 'both'.
    """
    cmds = {
        "black": ["black", target_path],
        "flake8": ["flake8", target_path],
    }

    if formatter == "both":
        for tool in ("black", "flake8"):
            LOG.info(f"Running {tool} on {target_path}...")
            try:
                subprocess.run(cmds[tool], check=False)
            except FileNotFoundError:
                LOG.warning(f"{tool} not found. Please install it or use `pip install .[format]`.")
    else:
        LOG.info(f"Running {formatter} on {target_path}...")
        try:
            subprocess.run(cmds[formatter], check=False)
        except FileNotFoundError:
            LOG.warning(f"{formatter} not found. Please install it or use `pip install .[format]`.")

