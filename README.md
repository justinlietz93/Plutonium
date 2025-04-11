# Plutonium Dependency Analyzer

A cross-language dependency analysis tool that helps you track, compare, and auto-fix dependencies across multiple programming environments. The tool analyzes dependencies in Node.js, Python, Ruby, Maven (Java), and Go projects, generates a comprehensive Markdown report showing current versions compared to the latest available versions, and automatically resolves dependency conflicts and security vulnerabilities in the local development environment.

## Features

- **Cross-Language Support**: Analyzes dependencies in Node.js, Python, Ruby, Maven, and Go projects.
- **Version Comparison**: Compares current dependency versions with the latest available versions.
- **Auto-Fixing**: Automatically resolves dependency conflicts (e.g., version mismatches) and security vulnerabilities (e.g., by upgrading to secure versions using the NVD API).
- **Markdown Report**: Generates a detailed report with tables showing dependency statuses, conflict resolutions, and security fixes.
- **Extensible**: Easily add support for new programming languages by implementing new analyzers.

## Prerequisites

- **Python 3.12+**: Ensure Python 3.12 or higher is installed on your system.
- **External Tools** (only needed for languages you're analyzing):
  - **Node.js and npm**: For analyzing Node.js projects.
  - **pip**: For analyzing Python projects (included with Python 3.12).
  - **Ruby and Bundler**: For analyzing Ruby projects.
  - **Maven**: For analyzing Java projects.
  - **Go**: For analyzing Go projects.

### Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/justinlietz93/plutonium.git
   cd plutonium