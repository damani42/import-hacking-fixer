#!/usr/bin/env python3
"""Command-line interface for import-hacking-fixer using Click."""

from importlib import metadata
import logging
from pathlib import Path
import sys

import click
from import_hacking_fixer import core











try:
    VERSION = f"import-hacking-fixer {metadata.version('import_hacking_fixer')}"
except Exception:
    VERSION = "import-hacking-fixer"


def _handle_files(path: Path, project_packages: str, apply_changes: bool) -> int:
    """Process Python files and report or fix import issues.

    Args:
        path: File or directory to process.
        project_packages: Comma-separated list of top-level project packages.
        apply_changes: If True, apply fixes in place.
    Returns:
        0 if no changes, 1 if changes required, 2 if error occurred.
    """
    stdlib = core.get_stdlib_modules()
    project_pkgs = set(filter(None, (p.strip() for p in project_packages.split(","))))

    if not project_pkgs and path.is_dir():
        project_pkgs = core.find_project_packages(str(path))

    exit_code = 0
    total_warnings = 0

    # Handle single file or directory
    if path.is_file():
        file_paths = [path]
    else:
        file_paths = list(core.iter_python_files(str(path)))

    for file_path in file_paths:
        try:
            modified, warnings = core.process_file(str(file_path), stdlib, project_pkgs, apply=apply_changes)
        except Exception as exc:
            logging.error("[%s] ERROR: %s", file_path, exc)
            exit_code = max(exit_code, 2)
            continue

        for lineno, msg in warnings:
            logging.warning("[%s] line %s: %s", file_path, lineno, msg)
            total_warnings += 1

        if modified:
            msg = "file updated." if apply_changes else "imports would be modified."
            logging.info("[%s] %s", file_path, msg)
            exit_code = max(exit_code, 1)

    if total_warnings:
        logging.info("Total warnings: %d", total_warnings)

    return exit_code


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Increase verbosity.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-error output.")
@click.version_option(version=VERSION, prog_name="import-hacking-fixer CLI")
def cli(verbose: bool, quiet: bool) -> None:
    """Check and fix Python imports (OpenStack style)."""
    # Configure logging only once
    if not logging.getLogger().handlers:
        if quiet:
            logging.basicConfig(level=logging.ERROR, format="%(message)s")
        else:
            logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s")


@cli.command(help="Report import issues without modifying files.")
@click.argument("path", type=click.Path(exists=True, file_okay=True, dir_okay=True))
@click.option("--project-packages", default="", help="Comma-separated list of top-level project packages.")
def check(path: str, project_packages: str) -> None:
    exit_code = _handle_files(Path(path), project_packages, apply_changes=False)
    sys.exit(exit_code)


@cli.command(help="Fix import issues in place.")
@click.argument("path", type=click.Path(exists=True, file_okay=True, dir_okay=True))
@click.option("--project-packages", default="", help="Comma-separated list of top-level project packages.")
def fix(path: str, project_packages: str) -> None:
    exit_code = _handle_files(Path(path), project_packages, apply_changes=True)
    sys.exit(exit_code)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    cli()
