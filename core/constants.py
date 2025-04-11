"""
Constants module defining shared constants for the dependency analyzer.

This module centralizes all constant values used throughout the application,
making maintenance and updates easier.
"""

# Supported programming environments
SUPPORTED_ENVIRONMENTS = {
    "Node.js",
    "Python",
    "Ruby",
    "Maven",
    "Go"
}

# Mapping of environments to their dependency manifest files
DEPENDENCY_FILES = {
    "Node.js": "package.json",
    "Python": "requirements.txt",
    "Ruby": "Gemfile",
    "Maven": "pom.xml",
    "Go": "go.mod"
}

# API URLs for fetching latest package versions
API_URLS = {
    "npm": "https://registry.npmjs.org/{package}",
    "PyPI": "https://pypi.org/pypi/{package}/json",
    "RubyGems": "https://rubygems.org/api/v1/gems/{package}.json",
    "Maven": "https://search.maven.org/solrsearch/select?q=g:{group_id}+AND+a:{artifact_id}&wt=json",
    "Go": "https://proxy.golang.org/{package}/@v/list"
}

# Other constants
DEFAULT_TIMEOUT = 10  # seconds
CACHE_TTL = 86400  # 24 hours in seconds
DEFAULT_OUTPUT_FILE = "dependency_report.md"
