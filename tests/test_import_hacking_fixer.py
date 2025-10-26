import importlib.util
import os


def load_import_hacking_fixer():
    """Dynamically load the import_hacking_fixer module from the repository root."""
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'import_hacking_fixer.py'))
    spec = importlib.util.spec_from_file_location("import_hacking_fixer", script_path)
    import_hacking_fixer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(import_hacking_fixer)  # type: ignore
    return import_hacking_fixer


def test_process_file_sorts_and_splits_imports(tmp_path):
    import_hacking_fixer = load_import_hacking_fixer()
    # Example file with violations H301, H303 and H304
    content = """
import sys, os
from .local import module  # relative import
from math import sqrt, sin
from os.path import *
import logging
import random

def foo():
    pass
"""
    tmp_file = tmp_path / "example.py"
    tmp_file.write_text(content)
    stdlib = import_hacking_fixer.get_stdlib_modules()
    project_pkgs = set()
    # First pass: detect but do not apply
    modified, warnings = import_hacking_fixer.process_file(str(tmp_file), stdlib, project_pkgs, apply=False)
    assert any("H301" in w[1] for w in warnings)
    assert any("H303" in w[1] for w in warnings)
    assert any("H304" in w[1] for w in warnings)
    assert modified
    # Second pass: apply rewriting
    modified, warnings = import_hacking_fixer.process_file(str(tmp_file), stdlib, project_pkgs, apply=True)
    assert modified
    result = tmp_file.read_text().splitlines()
    expected_start = [
        "import logging",
        "from math import sin",
        "from math import sqrt",
        "import os",
        "import random",
        "import sys",
        ""
    ]
    assert result[:7] == expected_start


def test_classify_project_imports(tmp_path):
    import_hacking_fixer = load_import_hacking_fixer()
    # create a local package to test 'project' group
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    content = "import os\nimport mypkg.module\n"
    file_path = tmp_path / "f.py"
    file_path.write_text(content)
    stdlib = import_hacking_fixer.get_stdlib_modules()
    project_pkgs = {"mypkg"}
    modified, warnings = import_hacking_fixer.process_file(str(file_path), stdlib, project_pkgs, apply=True)
    assert modified
    new_content = file_path.read_text()
    # mypkg import should be converted to 'from mypkg import module'
    assert "import os" in new_content
    assert "from mypkg import module" in new_content
