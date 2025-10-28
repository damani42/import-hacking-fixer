#!/usr/bin/env python3
"""Test script to verify that ihf can completely fix import violations."""

import tempfile
import subprocess
import sys
from pathlib import Path

def test_complete_fix():
    """Test that ihf can completely fix all import violations."""
    
    # Create a test file with various import violations
    test_code = '''#!/usr/bin/env python3
"""Test file with import violations."""

import os, sys  # H301: multiple imports on one line
import importlib.util  # Should stay as import (special case)
from typing import Dict, List  # H301: multiple imports on one line
from pathlib import Path
import logging
from import_hacking_fixer import core  # Local import mixed with stdlib
import ast
from collections import defaultdict

def test_function():
    """Test function."""
    return "test"
'''

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "test_imports.py"
        test_file.write_text(test_code)
        
        print("Original file:")
        print(test_file.read_text())
        print("\n" + "="*50 + "\n")
        
        # Run ihf check to see violations
        print("Running ihf check...")
        result = subprocess.run([
            sys.executable, "-m", "import_hacking_fixer.cli", 
            "check", str(test_file)
        ], capture_output=True, text=True)
        
        print("Check output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        print("\n" + "="*50 + "\n")
        
        # Run ihf fix to correct violations
        print("Running ihf fix...")
        result = subprocess.run([
            sys.executable, "-m", "import_hacking_fixer.cli", 
            "fix", str(test_file)
        ], capture_output=True, text=True)
        
        print("Fix output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        print("\n" + "="*50 + "\n")
        
        # Check the result
        print("Fixed file:")
        print(test_file.read_text())
        
        print("\n" + "="*50 + "\n")
        
        # Run ihf check again to see if all violations are fixed
        print("Running ihf check again...")
        result = subprocess.run([
            sys.executable, "-m", "import_hacking_fixer.cli", 
            "check", str(test_file)
        ], capture_output=True, text=True)
        
        print("Final check output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        # Check if there are any remaining violations
        if "warnings:" in result.stdout.lower() or "would be modified" in result.stdout:
            print("\n❌ FAILED: Still have violations!")
            return False
        else:
            print("\n✅ SUCCESS: All violations fixed!")
            return True

if __name__ == "__main__":
    success = test_complete_fix()
    sys.exit(0 if success else 1)
