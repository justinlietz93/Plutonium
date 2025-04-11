# setup.py
from setuptools import setup, find_packages

setup(
    name="plutonium",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "pytest>=7.0.0",
        "pyinstaller>=5.0.0",
        "black",
        "flake8",
        "mypy",
        "pipdeptree>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "dependency-analyzer=plutonium.main:main",
        ],
    },
    author="Justin Lietz",
    author_email="jlietz93@gmail.com",
    description="A tool to analyze and auto-fix dependencies across multiple programming environments",
    license="MIT",  # SPDX license expression
    python_requires=">=3.8",
)