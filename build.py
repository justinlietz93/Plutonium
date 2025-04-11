"""
Build script for the Plutonium Dependency Analyzer.

This script automates the installation of dependencies and packages the main.py script
into a single executable using PyInstaller.
"""

import subprocess
import sys
import os

def install_requirements():
    """Install dependencies from requirements.txt."""
    print("Installing dependencies from requirements.txt...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

def install_package():
    """Install the Plutonium package."""
    print("Installing the Plutonium package...")
    subprocess.run([sys.executable, "-m", "pip", "install", "."], check=True)

def build_executable():
    """Package main.py into a single executable using PyInstaller."""
    print("Building executable with PyInstaller...")
    # Path to the site-packages/plutonium directory
    site_packages_plutonium = os.path.join(sys.prefix, "Lib", "site-packages", "plutonium")
    # Ensure version_cache.json exists
    if not os.path.exists("version_cache.json"):
        print("Creating empty version_cache.json")
        with open("version_cache.json", "w") as f:
            f.write("{}")
    subprocess.run([
        "pyinstaller",
        "--onefile",
        "--path", site_packages_plutonium,
        "--hidden-import", "plutonium",
        "--hidden-import", "plutonium.core",
        "--hidden-import", "plutonium.core.generator",
        "--hidden-import", "plutonium.core.logging",
        "--hidden-import", "plutonium.core.constants",
        "--hidden-import", "plutonium.core.exceptions",
        "--hidden-import", "plutonium.analyzers",
        "--hidden-import", "plutonium.analyzers.interface",
        "--hidden-import", "plutonium.analyzers.nodejs_analyzer",
        "--hidden-import", "plutonium.analyzers.python_analyzer",
        "--hidden-import", "plutonium.analyzers.ruby_analyzer",
        "--hidden-import", "plutonium.analyzers.maven_analyzer",
        "--hidden-import", "plutonium.analyzers.go_analyzer",
        "--add-data", "config.json;.",
        "--add-data", "version_cache.json;.",  # Ensure cache file is included
        "main.py"
    ], check=True)
    print("Executable created in dist/ directory.")

def build():
    """Run the full build process: install dependencies, install package, and build executable."""
    try:
        install_requirements()
        install_package()
        build_executable()
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()