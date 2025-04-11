#!/usr/bin/env python3
"""
Build script for creating the Plutonium executable.

This script uses PyInstaller to build a standalone executable
that correctly handles the package imports.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path


def build_executable():
    """Build the executable using PyInstaller."""
    print("Building Plutonium executable...")
    
    # Clean any previous build artifacts
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    # Build the executable with PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",                   # Create a single executable file
        "--name", "plutonium",         # Name of the executable
        "--clean",                     # Clean PyInstaller cache
        "--log-level", "INFO",         # Log level
        "--add-data", "config.json;.", # Include config.json in the executable
        "--paths", ".",                # Add current directory to Python path
        "--hidden-import", "plutonium",  # Make sure plutonium is included
        "--hidden-import", "plutonium.core.constants",  # Explicitly include modules
        "--hidden-import", "plutonium.core.generator",
        "--collect-submodules", "plutonium",  # Collect all submodules in plutonium
        "main.py"                      # The entry point script
    ]
    
    # Use semicolons on Windows and colons on other platforms
    if platform.system() != "Windows":
        cmd[9] = "config.json:."
    
    # Run PyInstaller
    subprocess.run(cmd, check=True)
    
    print("Build completed successfully.")
    print(f"Executable created at: {os.path.abspath(os.path.join('dist', 'plutonium'))}")


if __name__ == "__main__":
    build_executable()
