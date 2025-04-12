"""
Python dependency analyzer module.

This module provides functionality to analyze Python dependencies
by parsing requirements.txt files, fetching latest versions from PyPI,
and checking vulnerabilities using the VulnCheck API.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import time # For potential rate limiting delays

import requests

# Use relative imports within the package
from .interface import IDependencyAnalyzer
# Assuming constants are now in plutonium.core
from ..core.constants import API_URLS, DEFAULT_TIMEOUT, VULNCHECK_API_TOKEN_ENV_VAR
from ..core.exceptions import NetworkError, ParsingError, ConfigurationError
from ..core.cache import VersionCache
import os # To read token


class PythonAnalyzer(IDependencyAnalyzer):
    """Analyzer for Python dependencies."""

    def __init__(self, cache: Optional[VersionCache] = None, vulncheck_api_token: Optional[str] = None):
        """
        Initialize the PythonAnalyzer.

        Args:
            cache: Optional VersionCache instance.
            vulncheck_api_token: Optional VulnCheck API token.
        """
        super().__init__(cache) # Call parent __init__ if it exists and takes cache
        self.logger = logging.getLogger("analyzer.Python")
        self.vulncheck_api_token = vulncheck_api_token
        self.vulncheck_headers = None
        if self.vulncheck_api_token:
            self.vulncheck_headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.vulncheck_api_token}'
            }
        else:
             self.logger.warning(
                 f"VulnCheck API token not provided to PythonAnalyzer. "
                 "Vulnerability information will not be fetched."
             )

    @property
    def environment_name(self) -> str:
        return "Python"

    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Python package from PyPI.

        Args:
            package_name: The name of the package

        Returns:
            The latest version as a string or 'N/A' if lookup fails.

        Raises:
            NetworkError: If there's a network issue fetching the latest version.
            ParsingError: If the PyPI response cannot be parsed.
        """
        # Check cache first
        cached_version = self.cache.get(package_name)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version

        # Fetch from PyPI
        url = API_URLS["PyPI"].format(package=package_name)
        self.logger.debug(f"Fetching latest version for {package_name} from {url}")
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 404:
                 self.logger.warning(f"Package {package_name} not found on PyPI (404).")
                 return "N/A (Not Found)"
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            latest_version = data.get("info", {}).get("version", "N/A (Parse Error)")
            if latest_version != "N/A (Parse Error)":
                 self.cache.set(package_name, latest_version) # Cache successful lookups
            return latest_version
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching latest version for {package_name} from PyPI.")
            raise NetworkError(f"Timeout fetching latest version for {package_name} from PyPI.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching latest version for {package_name} from PyPI: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {package_name} from PyPI: {str(e)}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"Error parsing PyPI response for {package_name}: {str(e)}")
            raise ParsingError(f"Failed to parse latest version for {package_name} from PyPI: {str(e)}")
        except Exception as e:
             self.logger.error(f"Unexpected error fetching latest version for {package_name}: {str(e)}", exc_info=True)
             return "N/A (Error)"

    def _fetch_vulnerabilities(self, package_name: str, version: str) -> List[str]:
        """
        Fetch vulnerabilities for a specific package version using VulnCheck API (PURL).

        Args:
            package_name: The name of the package.
            version: The specific version of the package.

        Returns:
            A list of vulnerability IDs (e.g., CVEs) or an empty list if none found or error.
        """
        if not self.vulncheck_headers:
            self.logger.debug("Skipping vulnerability check: VulnCheck token not available.")
            return ["N/A (No Token)"]

        # Construct Package URL (PURL)
        purl = f"pkg:pypi/{package_name}@{version}"
        url = API_URLS["VulnCheck_PURL"]
        params = {'purl': purl}

        self.logger.debug(f"Fetching vulnerabilities for {purl} from {url}")
        try:
            # Implement basic rate limiting delay if needed
            # time.sleep(0.1) # Example: sleep 100ms between API calls

            response = requests.get(url, headers=self.vulncheck_headers, params=params, timeout=DEFAULT_TIMEOUT)

            if response.status_code == 401:
                 self.logger.error(f"VulnCheck API Error 401: Unauthorized. Check your API token.")
                 return ["Error (Unauthorized)"]
            if response.status_code == 403:
                 self.logger.error(f"VulnCheck API Error 403: Forbidden. Check permissions or rate limits.")
                 return ["Error (Forbidden)"]
            if response.status_code == 429:
                 self.logger.warning(f"VulnCheck API Error 429: Rate limit exceeded for {purl}. Consider adding delays.")
                 return ["Error (Rate Limit)"]

            response.raise_for_status() # Raise for other bad status codes

            data = response.json()
            vulnerabilities = []
            # Parse the response - adjust based on actual VulnCheck API structure
            # Assuming the response is a list of vulnerability objects, each with an 'id'
            if isinstance(data, list):
                 for vuln in data:
                      if isinstance(vuln, dict) and 'id' in vuln:
                           vulnerabilities.append(vuln['id'])
            elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                 # Handle potential pagination or wrapper objects
                 for vuln in data['data']:
                     if isinstance(vuln, dict) and 'id' in vuln:
                          vulnerabilities.append(vuln['id'])
            else:
                self.logger.warning(f"Unexpected VulnCheck API response format for {purl}: {data}")


            self.logger.debug(f"Found {len(vulnerabilities)} vulnerabilities for {purl}")
            return vulnerabilities if vulnerabilities else [] # Return empty list if none found

        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching vulnerabilities for {purl} from VulnCheck.")
            return ["Error (Timeout)"]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching vulnerabilities for {purl} from VulnCheck: {str(e)}")
            return ["Error (Network)"]
        except (ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"Error parsing VulnCheck response for {purl}: {str(e)}")
            return ["Error (Parse)"]
        except Exception as e:
             self.logger.error(f"Unexpected error fetching vulnerabilities for {purl}: {str(e)}", exc_info=True)
             return ["Error (Unexpected)"]

    def analyze_dependencies(self, directory: str) -> List[Tuple[str, str, str, List[str]]]:
        """
        Analyze Python dependencies defined in requirements.txt.

        Args:
            directory: The directory containing the requirements.txt file.

        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities).

        Raises:
            FileNotFoundError: If requirements.txt doesn't exist.
            ParsingError: If requirements.txt cannot be parsed.
            NetworkError: If latest versions cannot be fetched.
        """
        self.logger.info(f"Analyzing Python dependencies in {directory}")

        dependency_file = self._get_dependency_file_path(directory)
        dependencies_in_file = self._parse_dependencies(dependency_file)

        results = []
        self.logger.info(f"Processing {len(dependencies_in_file)} dependencies from {dependency_file.name}")
        for package, current_version in dependencies_in_file.items():
            latest_version = "Error"
            vulnerabilities = ["N/A"] # Default
            # Check if version is specific BEFORE calling checker
            is_specific_version = current_version and current_version not in ["(Complex Specifier)", "unknown", "N/A"] and not current_version.startswith("${")

            if self.vulnerability_checker and is_specific_version and latest_version != "Error":
                try:
                    # This will now return ["N/A (Skipped)"] because of the changes above
                    vulnerabilities = self.vulnerability_checker.fetch_vulnerabilities(
                        package, current_version, self.environment_name
                    )
                except Exception as e:
                    self.logger.error(f"Vulnerability check call failed for {package}@{current_version}: {e}")
                    vulnerabilities = ["Error (Check Failed)"]
            elif not is_specific_version:
                # Set specific status for invalid versions - checker is not called
                vulnerabilities = ["N/A (Version Invalid/Range)"]
            # else: # Handle checker missing or latest_version error

            results.append((package, current_version, latest_version, vulnerabilities))

        self.logger.info(f"Finished processing Python dependencies for {directory}. Found {len(results)} results.")
        return results

    def _get_dependency_file_path(self, directory: str) -> Path:
        """Get the path to the requirements.txt file."""
        file_path = Path(directory) / "requirements.txt"
        if not file_path.exists():
            self.logger.error(f"requirements.txt not found in {directory}")
            raise FileNotFoundError(f"requirements.txt not found in {directory}")
        return file_path

    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """Parse the requirements.txt file."""
        self.logger.debug(f"Parsing dependencies from {file_path}")
        dependencies = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-'):
                    # Skip empty lines, comments, and options like -r, -e
                    continue

                # Handle basic '==' specifier
                if '==' in line:
                    parts = line.split('==', 1)
                    package = parts[0].strip()
                    # Handle potential environment markers like 'package==1.0; python_version < "3.8"'
                    if ';' in package:
                         package = package.split(';', 1)[0].strip()
                    # Handle potential extras like 'package[extra]==1.0'
                    if '[' in package and ']' in package:
                         package = package.split('[', 1)[0].strip()

                    version = parts[1].strip()
                    if ';' in version:
                         version = version.split(';', 1)[0].strip() # Remove markers from version too

                    if package: # Ensure we have a package name after stripping
                        dependencies[package] = version
                    else:
                         self.logger.warning(f"Could not parse package name from line {line_num} in {file_path.name}: '{line}'")

                # Handle '>=' or '~=' - take the package name, version is 'complex'
                elif '>=' in line or '~=' in line or '<=' in line or '<' in line or '>' in line:
                     # For now, just extract package name and mark version as complex
                     # A more robust parser (like `pkg_resources` or `packaging`) would be better
                     specifiers = ['>=', '~=', '<=', '<', '>']
                     package = line
                     for spec in specifiers:
                          if spec in package:
                               package = package.split(spec, 1)[0].strip()
                               break # Use the first specifier found

                     if ';' in package:
                         package = package.split(';', 1)[0].strip()
                     if '[' in package and ']' in package:
                         package = package.split('[', 1)[0].strip()

                     if package:
                        dependencies[package] = "(Complex Specifier)" # Cannot check specific version
                        self.logger.debug(f"Treating line {line_num} as complex specifier for package '{package}'")
                     else:
                         self.logger.warning(f"Could not parse package name from complex specifier on line {line_num} in {file_path.name}: '{line}'")

                else:
                    # Assume it's a package name without version (get latest?) - For now, skip.
                    self.logger.warning(f"Skipping line {line_num} in {file_path.name} (no recognized version specifier): '{line}'")

            self.logger.debug(f"Parsed {len(dependencies)} dependencies from {file_path.name}")
            return dependencies
        except IOError as e:
            self.logger.error(f"Error reading {file_path.name}: {str(e)}")
            raise ParsingError(f"Failed to read {file_path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing {file_path.name}: {str(e)}", exc_info=True)
            raise ParsingError(f"Unexpected error parsing {file_path.name}: {str(e)}")