#!/usr/bin/env python3
"""Test script to compare our logic with hacking's logic."""

import tempfile
import subprocess
import sys
from pathlib import Path

def test_hacking_vs_ihf():
    """Compare hacking and ihf detection on various import patterns."""
    
    test_cases = [
        # Case 1: Multiple imports on one line (H301)
        {
            'name': 'H301 - Multiple imports',
            'code': '''import os, sys
import logging''',
            'expected_h301': True
        },
        
        # Case 2: Multiple from imports (H301, H302)
        {
            'name': 'H301/H302 - Multiple from imports',
            'code': '''from typing import Dict, List
import os''',
            'expected_h301': True,
            'expected_h302': True
        },
        
        # Case 3: Alphabetical order (H306)
        {
            'name': 'H306 - Alphabetical order',
            'code': '''import sys
import os
import logging''',
            'expected_h306': True
        },
        
        # Case 4: Mixed import types alphabetical
        {
            'name': 'H306 - Mixed import types',
            'code': '''import sys
from collections import defaultdict
import os''',
            'expected_h306': True
        },
        
        # Case 5: Wildcard import (H303)
        {
            'name': 'H303 - Wildcard import',
            'code': '''from os import *
import sys''',
            'expected_h303': True
        },
        
        # Case 6: Relative import (H304)
        {
            'name': 'H304 - Relative import',
            'code': '''from .module import something
import os''',
            'expected_h304': True
        }
    ]
    
    print("🧪 Testing hacking vs ihf detection logic...")
    print("=" * 60)
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['name']}")
        print("-" * 40)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text(test_case['code'])
            
            # Test with hacking
            print("🔍 Hacking detection:")
            try:
                result = subprocess.run([
                    sys.executable, "-m", "flake8", str(test_file), "--select=H"
                ], capture_output=True, text=True, timeout=10)
                
                hacking_output = result.stdout.strip()
                if hacking_output:
                    print(f"  ✅ Found violations: {hacking_output}")
                else:
                    print("  ✅ No violations found")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                hacking_output = ""
            
            # Test with ihf
            print("🔍 IHF detection:")
            try:
                result = subprocess.run([
                    sys.executable, "-m", "import_hacking_fixer.cli", 
                    "check", str(test_file)
                ], capture_output=True, text=True, timeout=10)
                
                ihf_output = result.stdout.strip()
                if ihf_output:
                    print(f"  ✅ Found violations: {ihf_output}")
                else:
                    print("  ✅ No violations found")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                ihf_output = ""
            
            # Compare results
            print("📊 Comparison:")
            hacking_violations = set()
            ihf_violations = set()
            
            # Parse hacking violations
            for line in hacking_output.split('\n'):
                if 'H301' in line:
                    hacking_violations.add('H301')
                if 'H302' in line:
                    hacking_violations.add('H302')
                if 'H303' in line:
                    hacking_violations.add('H303')
                if 'H304' in line:
                    hacking_violations.add('H304')
                if 'H306' in line:
                    hacking_violations.add('H306')
            
            # Parse ihf violations
            for line in ihf_output.split('\n'):
                if 'H301' in line:
                    ihf_violations.add('H301')
                if 'H302' in line:
                    ihf_violations.add('H302')
                if 'H303' in line:
                    ihf_violations.add('H303')
                if 'H304' in line:
                    ihf_violations.add('H304')
                if 'H306' in line:
                    ihf_violations.add('H306')
            
            print(f"  Hacking violations: {hacking_violations}")
            print(f"  IHF violations: {ihf_violations}")
            
            if hacking_violations == ihf_violations:
                print("  ✅ MATCH: Both tools detect the same violations")
            else:
                print("  ❌ MISMATCH: Tools detect different violations")
                print(f"    Missing in IHF: {hacking_violations - ihf_violations}")
                print(f"    Extra in IHF: {ihf_violations - hacking_violations}")
                all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 SUCCESS: All tests passed! Our logic matches hacking's logic.")
    else:
        print("❌ FAILURE: Some tests failed. Logic needs improvement.")
    
    return all_passed

if __name__ == "__main__":
    success = test_hacking_vs_ihf()
    sys.exit(0 if success else 1)
