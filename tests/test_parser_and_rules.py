import ast

from import_hacking_fixer.parser import extract_imports_from_file
from import_hacking_fixer.rules import classify_import


def test_extract_imports_from_file(tmp_path):
    code = "import os\nfrom math import sqrt, sin\n"
    file = tmp_path / "sample.py"
    file.write_text(code)
    imports = extract_imports_from_file(str(file))
    # Ensure all returned nodes are import statements
    assert all(isinstance(node, (ast.Import, ast.ImportFrom)) for node in imports)
    # Should detect two import statements
    assert len(imports) == 2


def test_classify_imports(tmp_path):
    code = "import os\nimport random\nfrom mypkg import module\n"
    file = tmp_path / "sample2.py"
    file.write_text(code)
    imports = extract_imports_from_file(str(file))
    results = [classify_import(node) for node in imports]
    # 'os' and 'random' are stdlib, 'mypkg' should be classified as local
    assert results[0] == "stdlib"
    assert results[1] == "stdlib"
    assert results[2] == "local"
