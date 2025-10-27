#!/usr/bin/env python3
import argparse
import os
from import_hacking_fixer import core


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check and fix Python imports (OpenStack style)."
    )
    parser.add_argument(
        "--version",
        action="version",
        version="import-hacking-fixer CLI",
        help="display version information and exit",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'check' subcommand: report import issues without modifying files
    check_parser = subparsers.add_parser("check", help="report import issues")
    check_parser.add_argument("path", help="file or directory to process")
    check_parser.add_argument(
        "--project-packages",
        default="",
        help="comma-separated list of top-level project packages",
    )

    # 'fix' subcommand: modify files in place
    fix_parser = subparsers.add_parser("fix", help="fix import issues in place")
    fix_parser.add_argument("path", help="file or directory to process")
    fix_parser.add_argument(
        "--project-packages",
        default="",
        help="comma-separated list of top-level project packages",
    )

    return parser.parse_args()


def run(command: str, path: str, project_packages: str) -> int:
    # Build stdlib and project package sets
    stdlib = core.get_stdlib_modules()
    project_pkgs = set(filter(None, (p.strip() for p in project_packages.split(","))))
    if not project_pkgs and os.path.isdir(path):
        project_pkgs = core.find_project_packages(path)

    apply_changes = command == "fix"
    exit_code = 0
    for file_path in core.iter_python_files(path):
        modified, warnings = core.process_file(
            file_path, stdlib, project_pkgs, apply=apply_changes
        )
        for lineno, msg in warnings:
            print(f"[{file_path}] line {lineno}: {msg}")
        if modified:
            exit_code = 1
            if apply_changes:
                print(f"[{file_path}] file updated.")
            else:
                print(f"[{file_path}] imports would be modified.")
    return exit_code


def main() -> None:
    args = parse_args()
    exit_code = run(
        args.command,
        args.path,
        getattr(args, "project_packages", ""),
    )
    # exit code indicates whether modifications were/are needed
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
