#!/usr/bin/env python3
import argparse
import os

import import_hacking_fixer.core as core


def main() -> None:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Check and fix Python imports (OpenStack style)."
    )
    parser.add_argument("path", help="file or directory to process")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite files instead of only reporting",
    )
    parser.add_argument(
        "--project-packages",
        default="",
        help="comma-separated list of top-level project packages",
    )
    args = parser.parse_args()
    stdlib = core.get_stdlib_modules()
    project_pkgs = set(
        filter(None, (p.strip() for p in args.project_packages.split(",")))
    )
    if not project_pkgs and os.path.isdir(args.path):
        project_pkgs = core.find_project_packages(args.path)
    for file_path in core.iter_python_files(args.path):
        modified, warnings = core.process_file(
            file_path, stdlib, project_pkgs, apply=args.apply
        )
        for lineno, msg in warnings:
            print(f"[{file_path}] line {lineno}: {msg}")
        if modified:
            if args.apply:
                print(f"[{file_path}] file updated.")
            else:
                print(f"[{file_path}] imports would be modified.")


if __name__ == "__main__":
    main()
