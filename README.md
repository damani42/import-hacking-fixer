# import-hacking-fixer
Command-line tool to check and fix Python imports according to OpenStack hacking rules.

## Installation

To install this project locally, clone the repository and run:

```bash
pip install .
```

This installs the `import_hacking_fixer` module and registers the `ihf` command-line tool in your PATH. Use `ihf` to check and fix Python imports.

To run the test suite using tox (which creates a virtual environment and runs pytest), install tox and run:

```bash
tox
```

This will execute the tests defined in the `tests/` directory.
