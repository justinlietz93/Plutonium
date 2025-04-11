# Contributing to Dependency Analyzer

Thank you for your interest in contributing to the Dependency Analyzer project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Setting Up the Development Environment](#setting-up-the-development-environment)
- [Coding Standards](#coding-standards)
- [Running Tests](#running-tests)
- [Adding Support for a New Language](#adding-support-for-a-new-language)
- [Branching Strategy](#branching-strategy)
- [Pull Request Process](#pull-request-process)

## Setting Up the Development Environment

1. **Fork and Clone the Repository**

   ```bash
   # Fork the repository on GitHub first, then clone your fork
   git clone https://github.com/your-username/dependency-analyzer.git
   cd dependency-analyzer
   ```

2. **Create a Virtual Environment**

   ```bash
   # Using venv
   python -m venv venv
   
   # Activate the virtual environment
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install Development Dependencies**

   ```bash
   pip install -r requirements-dev.txt
   ```

   Note: If `requirements-dev.txt` doesn't exist, you can install the necessary development tools manually:

   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-cov black flake8 mypy
   ```

4. **Install Pre-commit Hooks (Optional)**

   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Coding Standards

We follow standard Python best practices with some specific requirements:

### Code Formatting

- Use [Black](https://black.readthedocs.io/) for code formatting with a line length of 88 characters:

  ```bash
  black plutonium/
  ```

### Linting

- Use [Flake8](https://flake8.pycqa.org/) for linting:

  ```bash
  flake8 plutonium/
  ```

### Type Checking

- Use [MyPy](https://mypy.readthedocs.io/) for static type checking:

  ```bash
  mypy plutonium/
  ```

- All new code should include type hints.

### Documentation

- All modules, classes, and functions should have docstrings following the [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Update relevant documentation when making changes.

### Imports

- Organize imports in the following order:
  1. Standard library imports
  2. Related third-party imports
  3. Local application/library-specific imports
- Within each group, sort imports alphabetically.

### Error Handling

- Use the custom exception types defined in `..core/exceptions.py`.
- Include meaningful error messages.
- Log relevant information for debugging.

## Running Tests

We use pytest for testing. To run the tests:

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=plutonium tests/

# Generate coverage report
pytest --cov=plutonium --cov-report=html tests/
```

### Writing Tests

- All new features should include tests.
- Tests should be placed in the `tests/` directory with a filename matching the module being tested (e.g., `test_cache.py` for `..core/cache.py`).
- Use fixtures and mocks appropriately to avoid external dependencies in unit tests.

## Adding Support for a New Language

To add support for a new programming language or dependency management system:

1. **Create a New Analyzer Class**

   Create a new file in the `analyzers` directory (e.g., `php_analyzer.py`):

   ```python
   from .interface import IDependencyAnalyzer
   from ..core.exceptions import ParsingError, NetworkError

   class PhpAnalyzer(IDependencyAnalyzer):
       @property
       def environment_name(self) -> str:
           return "PHP"
       
       def get_latest_version(self, package_name: str) -> str:
           # Implement fetching the latest version from Packagist
           ...
       
       def analyze_dependencies(self, directory: str, output_file: str) -> None:
           # Implement dependency analysis for composer.json
           ...
   ```

2. **Update Constants**

   In `..core/constants.py`, add your new environment:

   ```python
   # Add to SUPPORTED_ENVIRONMENTS
   SUPPORTED_ENVIRONMENTS = {
       "Node.js",
       "Python",
       "Ruby",
       "Maven",
       "Go",
       "PHP"  # Add the new environment
   }
   
   # Add to DEPENDENCY_FILES
   DEPENDENCY_FILES = {
       "Node.js": "package.json",
       "Python": "requirements.txt",
       "Ruby": "Gemfile",
       "Maven": "pom.xml",
       "Go": "go.mod",
       "PHP": "composer.json"  # Add the dependency file
   }
   
   # Add to API_URLS
   API_URLS = {
       "npm": "https://registry.npmjs.org/{package}",
       # ...
       "Packagist": "https://repo.packagist.org/p2/{package}.json"  # Add the API URL
   }
   ```

3. **Update Factory**

   In `..core/factory.py`, update the `create_analyzers` method to create instances of your new analyzer:

   ```python
   # First, import your new analyzer
   from ..analyzers.php_analyzer import PhpAnalyzer
   
   # Then, in the create_analyzers method, add a new condition
   if env == "PHP":
       analyzer = PhpAnalyzer(cache)
   ```

4. **Write Tests**

   Create a new test file `tests/test_php_analyzer.py` that tests your analyzer implementation.

5. **Update Documentation**

   Update relevant documentation files to include the new language support.

## Branching Strategy

We follow a simplified Git workflow:

1. **Main Branch**: `main` branch contains the stable version of the code.
2. **Feature Branches**: Create feature branches for new features or bug fixes.

```bash
# Creating a new feature branch
git checkout -b feature/your-feature-name

# Creating a bug fix branch
git checkout -b fix/bug-description
```

## Pull Request Process

1. **Create a Pull Request**

   - Push your branch to your fork on GitHub.
   - Create a Pull Request against the `main` branch of the original repository.
   - Use a clear and descriptive title.
   - Provide a detailed description of the changes.

2. **Pull Request Template**

   When creating a pull request, please include:
   
   - A reference to the issue the PR addresses (if applicable)
   - A description of the changes
   - Any breaking changes
   - Screenshots or examples (if applicable)
   - Checklist of completed items

3. **Code Review**

   - All PRs require at least one review.
   - Address all review comments.
   - Make sure all CI checks pass.

4. **Merge**

   - Once the PR is approved and all checks pass, it will be merged.
   - The feature branch will be deleted after merging.

## Code of Conduct

Please be respectful and constructive in all interactions. We want to maintain a welcoming and inclusive community.

Thank you for contributing to the Dependency Analyzer project!
