# LLM Prompt: Create a build script using PyInstaller to package main.py into a single executable.
# 1. Import subprocess.
# 2. Define a function `build_executable()`.
# 3. Inside the function, use `subprocess.run` to execute `pyinstaller --onefile main.py`. Include `check=True`.
# 4. Add an `if __name__ == "__main__":` block to call `build_executable()`.
# 5. Ensure PyInstaller is listed in requirements.txt.
# Note: Packaging might require adjustments based on specific dependencies or data files.

