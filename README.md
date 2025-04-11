# Plutoneum Dependency Analyzer

A cross-language dependency analysis tool that helps you track and compare your project dependencies across multiple programming environments. The tool analyzes dependencies in Node.js, Python, Ruby, Maven (Java), and Go projects, and generates a comprehensive Markdown report showing current versions compared to the latest available versions.

## Prerequisites

- **Python 3.7+**
- **External tools** (only needed for languages you're analyzing):
  - **Node.js**: For analyzing Node.js projects
  - **pip**: For analyzing Python projects
  - **Ruby/Bundler**: For analyzing Ruby projects
  - **Maven**: For analyzing Java projects
  - **Go**: For analyzing Go projects

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/justinlietz93/plutoneum.git
   cd plutoneum
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

The tool is configured through a `config.json` file in the project root. Here's an example:

```json
{
  "OutputFile": "dependency_report.md",
  "Directories": [
    {
      "Path": "/path/to/nodejs/project",
      "Environments": ["Node.js"]
    },
    {
      "Path": "/path/to/python/project",
      "Environments": ["Python"]
    },
    {
      "Path": "/path/to/mixed/project",
      "Environments": ["Node.js", "Python", "Ruby", "Maven", "Go"]
    }
  ]
}
```

### Configuration Options

- `OutputFile`: (string) Path to the output report file.
- `Directories`: (array) List of directories to analyze.
  - `Path`: (string) Path to the directory containing the project.
  - `Environments`: (array) List of environments to analyze in this directory. Valid values are: `"Node.js"`, `"Python"`, `"Ruby"`, `"Maven"`, `"Go"`.

## Usage

Run the tool with the default configuration file:

```
python main.py
```

Or specify a custom configuration file:

```
python main.py -c custom_config.json
```

Additional options:

```
python main.py --help
```

## Output

The tool generates a Markdown report at the location specified in the `OutputFile` configuration. The report includes:

- A header with timestamp
- A section for each directory and environment combination
- Tables showing each dependency with its current and latest version
- Status indicators: ✅ (up to date) or ⚠️ (update available)
- A summary section

Example report:

```markdown
# Dependency Analysis Report

Generated on: 2025-04-10 22:50:30

This report shows the current and latest versions of dependencies across projects.

---

## Node.js Dependencies in /path/to/nodejs/project

| Package | Current Version | Latest Version |
|---------|----------------|----------------|
| express | 4.17.1 | 4.18.2 ⚠️ |
| lodash | 4.17.15 | 4.17.21 ⚠️ |
| react | 17.0.2 | 18.2.0 ⚠️ |

## Python Dependencies in /path/to/python/project

| Package | Current Version | Latest Version |
|---------|----------------|----------------|
| requests | 2.25.1 | 2.31.0 ⚠️ |
| flask | 2.0.1 | 2.3.3 ⚠️ |
| numpy | 1.21.0 | 1.26.4 ⚠️ |

---

## Report Summary

- ✅ = Up to date
- ⚠️ = Update available

---

Report complete.
```

## Project Structure

```
dependency_analyzer/
├── analyzers/               # Language-specific analyzers
│   ├── interface.py         # Base analyzer interface
│   ├── nodejs_analyzer.py   # Node.js dependency analyzer
│   ├── python_analyzer.py   # Python dependency analyzer
│   ├── ruby_analyzer.py     # Ruby dependency analyzer
│   ├── maven_analyzer.py    # Maven dependency analyzer
│   └── go_analyzer.py       # Go dependency analyzer
├── core/                    # Core functionality
│   ├── cache.py             # Version caching
│   ├── config_validator.py  # Configuration validation
│   ├── constants.py         # Shared constants
│   ├── exceptions.py        # Custom exceptions
│   ├── factory.py           # Analyzer factory
│   ├── generator.py         # Report generator
│   └── logging.py           # Logging setup
├── docs/                    # Documentation
│   ├── architecture.md      # Architecture documentation
│   └── contributing.md      # Contributing guidelines
├── tests/                   # Unit tests
├── config.json              # Configuration file
├── main.py                  # Main entry point
└── requirements.txt         # Python dependencies
```

## Extending

### Adding a New Language Analyzer

To add support for a new programming language:

1. Create a new file in the `analyzers` directory (e.g., `php_analyzer.py`)
2. Implement a class that inherits from `IDependencyAnalyzer` and implements all required methods
3. Add the new environment to `SUPPORTED_ENVIRONMENTS` in `core/constants.py`
4. Add the dependency file mapping in `DEPENDENCY_FILES` in `core/constants.py`
5. Add the registry API URL in `API_URLS` in `core/constants.py`
6. Update the `DependencyAnalyzerFactory.create_analyzers` method to create instances of your new analyzer

Example of a minimal analyzer implementation:

```python
from .interface import IDependencyAnalyzer
from ..core.exceptions import ParsingError

class NewLanguageAnalyzer(IDependencyAnalyzer):
    @property
    def environment_name(self) -> str:
        return "NewLanguage"
        
    def get_latest_version(self, package_name: str) -> str:
        # Implement fetching the latest version
        ...
        
    def analyze_dependencies(self, directory: str, output_file: str) -> None:
        # Implement dependency analysis
        ...
```

## Testing

Run the tests with pytest:

```
pytest tests/
```

Run tests with coverage:

```
pytest --cov=dependency_analyzer tests/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
