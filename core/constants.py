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

VULNCHECK_API_TOKEN_ENV_VAR = "VULNCHECK_API_KEY"

# API URLs for fetching latest package versions
API_URLS = {
    "NPM": "https://registry.npmjs.org/{package}",
    "PyPI": "https://pypi.org/pypi/{package}/json",
    "RubyGems": "https://rubygems.org/api/v1/gems/{package}.json",
    "Maven": "https://search.maven.org/solrsearch/select?q=g:{group_id}+AND+a:{artifact_id}&wt=json",
    "Go": "https://proxy.golang.org/{package}/@v/list",
    "VulnCheck_PURL": "https://api.vulncheck.com/v3/purl",
}

# Other constants
DEFAULT_TIMEOUT = 15  # seconds
CACHE_TTL = 86400  # 24 hours in seconds
DEFAULT_OUTPUT_FILE = "plutonium_report.md"
DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_LOG_FILE = "plutonium.log"