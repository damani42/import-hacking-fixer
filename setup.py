#!/usr/bin/env python3
import setuptools

setuptools.setup(
    name="import-hacking-fixer",
    version="0.1.0",
    packages=["import_hacking_fixer"],
    entry_points={
        "console_scripts": [
            "ihf = import_hacking_fixer.cli:main",
        ],
    },
    author="",
    description="Command-line tool to check and fix Python imports according to OpenStack hacking rules",
    license="MIT",
)
