#!/usr/bin/env python3
"""
Verify dependency split configuration.

This script checks that the dependency structure is correctly configured.
"""

import os
import sys
import tomllib


def check_file_exists(path, description):
    """Check if a file exists."""
    if os.path.exists(path):
        print(f"✓ {description}: {path}")
        return True
    else:
        print(f"✗ {description}: {path} NOT FOUND")
        return False


def check_requirements_file(path, expected_packages):
    """Check if requirements file contains expected packages."""
    if not os.path.exists(path):
        return False
    
    with open(path) as f:
        content = f.read().lower()
    
    for pkg in expected_packages:
        if pkg.lower() not in content:
            print(f"  ✗ Missing package: {pkg}")
            return False
    
    print(f"  ✓ Contains all expected packages")
    return True


def main():
    """Run verification checks."""
    print("ProjektKraken Dependency Structure Verification")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base_dir)
    
    all_good = True
    
    # Check requirements files exist
    print("\n1. Checking requirements files...")
    all_good &= check_file_exists("requirements.txt", "Main requirements")
    all_good &= check_file_exists("requirements-core.txt", "Core requirements")
    all_good &= check_file_exists("requirements-optional.txt", "Optional requirements")
    all_good &= check_file_exists("requirements-dev.txt", "Dev requirements")
    
    # Check core dependencies
    print("\n2. Checking core dependencies...")
    all_good &= check_requirements_file(
        "requirements-core.txt",
        ["PySide6", "Pillow", "python-dotenv"]
    )
    
    # Check optional dependencies
    print("\n3. Checking optional dependencies...")
    all_good &= check_requirements_file(
        "requirements-optional.txt",
        ["numpy", "requests", "fastapi", "uvicorn", "pyvis"]
    )
    
    # Check dev dependencies
    print("\n4. Checking dev dependencies...")
    all_good &= check_requirements_file(
        "requirements-dev.txt",
        ["pytest", "ruff", "mypy", "Sphinx"]
    )
    
    # Check main requirements includes others
    print("\n5. Checking main requirements structure...")
    with open("requirements.txt") as f:
        req_content = f.read()
    
    if all([
        "-r requirements-core.txt" in req_content,
        "-r requirements-optional.txt" in req_content,
        "-r requirements-dev.txt" in req_content
    ]):
        print("  ✓ Main requirements includes all sub-files")
    else:
        print("  ✗ Main requirements missing includes")
        all_good = False
    
    # Check pyproject.toml
    print("\n6. Checking pyproject.toml...")
    try:
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        
        # Check core dependencies
        core_deps = config["project"]["dependencies"]
        if len(core_deps) >= 3:
            print(f"  ✓ Core dependencies: {len(core_deps)} packages")
        else:
            print(f"  ✗ Core dependencies: only {len(core_deps)} packages (expected >=3)")
            all_good = False
        
        # Check optional groups
        optional = config["project"]["optional-dependencies"]
        required_groups = ["search", "webserver", "graph", "all", "dev"]
        for group in required_groups:
            if group in optional:
                print(f"  ✓ Optional group '{group}' defined")
            else:
                print(f"  ✗ Optional group '{group}' missing")
                all_good = False
    
    except Exception as e:
        print(f"  ✗ Error reading pyproject.toml: {e}")
        all_good = False
    
    # Check PyInstaller spec
    print("\n7. Checking PyInstaller spec...")
    if check_file_exists("ProjektKraken.spec", "PyInstaller spec"):
        with open("ProjektKraken.spec") as f:
            spec_content = f.read()
        
        if "excludes=[" in spec_content:
            # Count excludes
            exclude_count = spec_content.count("'pytest'") + \
                          spec_content.count("'sphinx'") + \
                          spec_content.count("'ruff'") + \
                          spec_content.count("'mypy'")
            if exclude_count > 0:
                print(f"  ✓ Excludes {exclude_count} dev packages")
            else:
                print("  ✗ No dev packages in excludes")
                all_good = False
        else:
            print("  ✗ No excludes list found")
            all_good = False
    else:
        all_good = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_good:
        print("✓ All checks passed!")
        return 0
    else:
        print("✗ Some checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
