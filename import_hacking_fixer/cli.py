#!/usr/bin/env python3
"""Command-line interface for import-hacking-fixer using click."""
import logging
from pathlib import Path
import importlib.metadata
import click

from import_hacking_fixer import core

# Determine version dynamically
try:
    VERSION = f"import-hacking-fixer {importlib.metadata.version('import_hacking_fixer')}"
except Exception:
    VERSION = "import-hacking-fixer"


def _handle_files(path: Path, project_packages: str, apply_changes: bool) -> int:
    """Process Python files under the given path and report/fix import issues.

    Args:
        path: A file or directory path to process.
        project_packages: A comma-separated list of top-level project packages.
        apply_changes: If True, apply fixes in place; otherwise just report.

    Returns:
        An exit code: 0 if no changes needed, 1 if changes were/are needed,
        or 2 if an error occurred while processing any file.
    """
    # Build stdlib and project package sets
    stdlib = core.get_stdlib_modules()
    project_pkgs = set(filter(None, (p.strip() for p in project_packages.split(","))))

    # If the user did not specify project packages and the path is a directory,
    # attempt to discover project packages from the path.
    if not project_pkgs and path.is_dir():
        project_pkgs = core.find_project_packages(str(path))

    exit_code = 0
    total_warnings = 0

    # Iterate over Python files using the core utility
    for file_path in core.iter_python_files(str(path)):
        try:
            modified, warnings = core.process_file(
                file_path, stdlib, project_pkgs, apply=apply_changes
            )
        except Exception as exc:
            logging.error(f"[{file_path}] ERROR: {exc}")
            exit_code = max(exit_code, 2)
            continue

        for lineno, msg in warnings:
            logging.warning(f"[{file_path}] line {lineno}: {msg}")
            total_warnings += 1

        if modified:
            if apply_changes:
                logging.info(f"[{file_path}] file updated.")
            else:
                logging.info(f"[{file_path}] imports would be modified.")
            exit_code = max(exit_code, 1)

    if total_warnings:
        logging.info(f"Total warnings: {total_warnings}")

    return exit_code

@click.group()
@click.option('-v', '--verbose', is_flag=True, help="Increase verbosity.")
@click.version_option(version=VERSION, prog_name="import-hacking-fixer CLI")
def cli(verbose: bool) -> None:
    """Check and fix Python imports (OpenStack style).

    This CLI provides two subcommands:

    - ``check``: report import issues without modifying files.
    - ``fix``: fix import issues in place.
    """
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s")


@cli.command(help="Report import issues without modifying files.")
@click.argument("path", type=click.Path(exists=True, file_okay=True, dir_okay=True))
@click.option("--project-packages", default="", help="Comma-separated list of top-level project packages.")
def check(path: str, project_packages: str) -> None:
    code = _handle_files(Path(path), project_packages, apply_changes=False)
    raise SystemExit(code)


@cli.command(help="Fix import issues in place.")
@click.argument("path", type=click.Path(exists=True, file_okay=True, dir_okay=True))
@click.option("--project-packages", default="", help="Comma-separated list of top-level project packages.")
def fix(path: str, project_packages: str) -> None:
    code = _handle_files(Path(path), project_packages, apply_changes=True)
    raise SystemExit(code)


if __name__ == "__main__":
    cli()
