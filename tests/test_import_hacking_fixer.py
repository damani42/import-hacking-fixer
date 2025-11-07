import import_hacking_fixer
from import_hacking_fixer.core import run_code_formatter

def test_run_code_formatter(monkeypatch):
    calls = []
    def fake_run(cmd, check):
        calls.append(cmd)
        return 0
    monkeypatch.setattr("subprocess.run", fake_run)
    run_code_formatter(".", "both")
    assert len(calls) == 2
    assert any("black" in c for c in calls)
    assert any("flake8" in c for c in calls)


def test_process_file_sorts_and_splits_imports(tmp_path):
    # create sample file with messy imports
    content = (
        "import sys\n"
        "import os\n"
        "import logging\n"
        "import random\n"
        "from math import sin, sqrt\n"
    )
    tmp_file = tmp_path / "f.py"
    tmp_file.write_text(content)
    stdlib = import_hacking_fixer.get_stdlib_modules()
    project_pkgs = set()

    # First pass: detect but do not apply
    modified, warnings = import_hacking_fixer.process_file(str(tmp_file), stdlib, project_pkgs, apply=False)
    assert any("Import order/style" in w[1] for w in warnings)
    assert modified

    # Second pass: apply rewriting
    modified, warnings = import_hacking_fixer.process_file(str(tmp_file), stdlib, project_pkgs, apply=True)
    assert modified

    result = tmp_file.read_text().splitlines()

    # Only check that imports are sorted alphabetically within stdlib
    expected_lines = [
        "import logging",
        "import os",
        "import random",
        "import sys",
        "from math import sin",
        "from math import sqrt",
    ]


    # Filter out empty lines for comparison
    cleaned_result = [line for line in result if line.strip()]
    assert cleaned_result == expected_lines


def test_classify_project_imports(tmp_path):
    # Create a local package to test 'project' group
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
