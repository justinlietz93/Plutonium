<p align="center">
  <img src="docs/plutonium-icon.png" alt="Plutonium Logo" width="200"/>
</p>

<h1 align="center">Plutonium</h1>

<p align="center">
  <strong>A cross-language dependency manager and analysis tool.</strong>
</p>

<p align="center">
  Plutonium helps you track, compare, and auto-fix dependencies across multiple programming environments. It analyzes dependencies in Node.js, Python, Ruby, Maven (Java), and Go projects, generates comprehensive Markdown reports comparing current vs. latest versions, and automatically resolves dependency conflicts and security vulnerabilities locally.
</p>

<p align="center">
  <a href="https://pypi.org/project/plutonium/">
    <img src="https://img.shields.io/pypi/v/plutonium?style=flat-square" alt="PyPI version"/>
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"/>
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg?style=flat-square" alt="Python 3.12+"/>
  </a>
</p>

## Key Features

* **Cross-Language Support**: Analyze dependencies for Node.js (npm), Python (pip), Ruby (Bundler), Java (Maven), and Go projects.
* **Version Comparison**: Identify outdated dependencies by comparing installed versions against the latest available releases.
* **Automated Remediation**: Resolve dependency conflicts (e.g., version mismatches) and security vulnerabilities (using NVD API integration) automatically.
* **Comprehensive Reporting**: Generate detailed Markdown reports outlining dependency statuses, conflicts resolved, and security fixes applied.
* **Extensible Architecture**: Designed for straightforward extension to support additional languages and package managers.

## Prerequisites

* **Python**: Version 3.12 or higher is required.
* **Language-Specific Toolchains**: Install the necessary tools only for the languages you intend to analyze:
    * **Node.js**: Node.js and npm
    * **Python**: pip (typically included with Python 3.4+)
    * **Ruby**: Ruby and Bundler
    * **Java**: Maven
    * **Go**: Go toolchain


---
