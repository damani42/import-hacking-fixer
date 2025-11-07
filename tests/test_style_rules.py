import tempfile
from pathlib import Path

from import_hacking_fixer.style_rules import read_line_length_config, check_line_length


def test_read_line_length_config_from_toml(tmp_path):
    toml = tmp_path / "pyproject.toml"
    toml.write_text("[tool.black]\nline-length = 88\n")
    value = read_line_length_config(str(tmp_path))
    assert value == 88


def test_check_line_length_detects_long_lines(tmp_path):
    f = tmp_path / "long_line.py"
    f.write_text("x = '" + "a" * 150 + "'\n")
    warnings = check_line_length(str(f), 79)
    assert warnings
    assert "E501" in warnings[0][1]

