"""
Node.js dependency analyzer module.

This module provides functionality to analyze Node.js dependencies
by parsing package-lock.json (preferred) or package.json files,
fetching the latest versions from NPM, and checking vulnerabilities
using the VulnCheck API.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import requests
import time # For potential rate limiting delays
import urllib.parse # For PURL encoding
import os # For reading token env var

# Use relative imports within the package
from .interface import IDependencyAnalyzer
# Assuming constants are now in plutonium.core
from ..core.constants import API_URLS, DEFAULT_TIMEOUT, VULNCHECK_API_TOKEN_ENV_VAR
from ..core.exceptions import NetworkError, ParsingError, ConfigurationError
from ..core.cache import VersionCache


class NodeJsAnalyzer(IDependencyAnalyzer):
    """Analyzer for Node.js dependencies."""

    def __init__(self, cache: Optional[VersionCache] = None, vulncheck_api_token: Optional[str] = None):
        """
        Initialize the NodeJsAnalyzer.

        Args:
            cache: Optional VersionCache instance.
            vulncheck_api_token: Optional VulnCheck API token.
        """
        super().__init__(cache) # Call parent __init__ if it exists and takes cache
        self.logger = logging.getLogger("analyzer.Node.js")
        self.vulncheck_api_token = vulncheck_api_token
        self.vulncheck_headers = None
        if self.vulncheck_api_token:
            self.vulncheck_headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.vulncheck_api_token}'
            }
        else:
             self.logger.warning(
                 f"VulnCheck API token not provided to NodeJsAnalyzer. "
                 "Vulnerability information will not be fetched."
             )

    @property
    def environment_name(self) -> str:
        return "Node.js"

    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Node.js package from npm.

        Args:
            package_name: The name of the package

        Returns:
            The latest version as a string or 'N/A' if lookup fails.

        Raises:
            NetworkError: If there's a network issue fetching the latest version.
            ParsingError: If the npm response cannot be parsed.
        """
        # Check cache first
        cached_version = self.cache.get(package_name)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version

        # Fetch from npm registry
        # URL encode package name, especially for scoped packages like @scope/name
        encoded_package_name = urllib.parse.quote(package_name, safe='')
        url = API_URLS["NPM"].format(package=encoded_package_name)
        self.logger.debug(f"Fetching latest version for {package_name} from {url}")

        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 404:
                 self.logger.warning(f"Package {package_name} not found on NPM (404).")
                 return "N/A (Not Found)"
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            # Look for the 'latest' tag in dist-tags
            latest_version = data.get("dist-tags", {}).get("latest", "N/A (Parse Error)")
            if latest_version != "N/A (Parse Error)":
                self.cache.set(package_name, latest_version) # Cache successful lookups
            return latest_version
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching latest version for {package_name} from NPM.")
            raise NetworkError(f"Timeout fetching latest version for {package_name} from NPM.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching latest version for {package_name} from NPM: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {package_name} from NPM: {str(e)}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"Error parsing NPM response for {package_name}: {str(e)}")
            raise ParsingError(f"Failed to parse latest version for {package_name} from NPM: {str(e)}")
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

        # Construct Package URL (PURL) for NPM
        # Handle scoped packages like @scope/name -> pkg:npm/%40scope/name@version
        purl_package_name = package_name
        if package_name.startswith('@'):
            scope, name = package_name.split('/', 1)
            # URL encode the scope part including the '@'
            purl_package_name = f"{urllib.parse.quote(scope)}/{name}"

        purl = f"pkg:npm/{purl_package_name}@{version}"
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
            if response.status_code == 404:
                 self.logger.debug(f"No vulnerability data found for {purl} (404).")
                 return [] # Not an error, just no data found
            if response.status_code == 429:
                 self.logger.warning(f"VulnCheck API Error 429: Rate limit exceeded for {purl}. Consider adding delays.")
                 return ["Error (Rate Limit)"]

            response.raise_for_status() # Raise for other bad status codes (5xx etc.)

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
        Analyze Node.js dependencies in the specified directory.
        Prefers package-lock.json for accurate versions, falls back to package.json.

        Args:
            directory: The directory containing package.json and potentially package-lock.json.

        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities).

        Raises:
            FileNotFoundError: If package.json doesn't exist.
            ParsingError: If dependency files cannot be parsed.
            NetworkError: If latest versions cannot be fetched.
        """
        self.logger.info(f"Analyzing Node.js dependencies in {directory}")

        package_json_path = self._get_dependency_file_path(directory) # Error if not found
        lock_file_path = Path(directory) / "package-lock.json"

        dependencies: Dict[str, str] = {}
        source_file = ""

        if lock_file_path.exists():
            try:
                dependencies = self._parse_dependencies(lock_file_path)
                source_file = lock_file_path.name
            except (ParsingError, FileNotFoundError, Exception) as e:
                 self.logger.warning(f"Failed to parse {lock_file_path.name}, falling back to {package_json_path.name}: {e}")
                 # Fall through to parsing package.json
                 dependencies = {} # Ensure dependencies are reset
        else:
            self.logger.info(f"{lock_file_path.name} not found, parsing dependencies from {package_json_path.name}.")

        # Fallback or if lockfile parsing failed
        if not dependencies:
             try:
                 # This provides declared versions, potentially ranges, less accurate for vuln checks
                 dependencies = self._parse_dependencies(package_json_path)
                 source_file = package_json_path.name
                 self.logger.warning(f"Using versions from {package_json_path.name}. Versions may be ranges; "
                                    f"vulnerability checks based on these might be less accurate.")
             except (ParsingError, FileNotFoundError, Exception) as e:
                  self.logger.error(f"Failed to parse {package_json_path.name} after lockfile failure/absence: {e}")
                  raise # Re-raise if we can't parse package.json either

        results = []
        self.logger.info(f"Processing {len(dependencies)} dependencies from {source_file}")

        for package, current_version in dependencies.items():
            latest_version = "Error"
            vulnerabilities = ["N/A"]
            try:
                latest_version = self.get_latest_version(package)

                # Check vulnerabilities based on the version we found (exact from lock, declared from json)
                # Avoid checking if version is clearly not a specific version
                if current_version and not any(c in current_version for c in '><^~* '):
                     vulnerabilities = self._fetch_vulnerabilities(package, current_version)
                elif latest_version not in ["N/A (Not Found)", "N/A (Parse Error)", "N/A (Error)"]:
                      # If current version is complex/missing, maybe check latest? Risky.
                      # For now, just mark as N/A if current_version isn't specific.
                      vulnerabilities = ["N/A (Version Range)"]
                else:
                    vulnerabilities = ["N/A (Version Lookup Failed)"]

            except (NetworkError, ParsingError, ValueError, Exception) as e:
                self.logger.error(f"Error processing dependency {package}=={current_version}: {str(e)}")
                latest_version = "Error" # Ensure latest_version reflects error state
                vulnerabilities = ["Error (Processing)"]

            results.append((package, current_version, latest_version, vulnerabilities))

        self.logger.info(f"Finished processing Node.js dependencies for {directory}. Found {len(results)} results.")
        return results

    def _get_dependency_file_path(self, directory: str) -> Path:
        """Get the path to the package.json file."""
        file_path = Path(directory) / "package.json"
        if not file_path.exists():
            self.logger.error(f"package.json not found in {directory}")
            raise FileNotFoundError(f"package.json not found in {directory}")
        return file_path

    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """Parse the package.json file (fallback method)."""
        self.logger.debug(f"Parsing dependencies from {file_path.name}")
        dependencies = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Include both dependencies and devDependencies
            # Note: These versions can be ranges (e.g., "^1.2.3", "~1.2.3")
            for dep_type in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                if dep_type in data and isinstance(data[dep_type], dict):
                    for package, version_range in data[dep_type].items():
                        # Store the declared version range/specifier
                        dependencies[package] = str(version_range)

            self.logger.debug(f"Parsed {len(dependencies)} dependency declarations from {file_path.name}")
            return dependencies
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Error parsing {file_path.name}: {str(e)}")
            raise ParsingError(f"Failed to parse {file_path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing {file_path.name}: {str(e)}", exc_info=True)
            raise ParsingError(f"Unexpected error parsing {file_path.name}: {str(e)}")

    def _parse_package_json(self, file_path: Path) -> Dict[str, str]:
        """Parse the package.json file (fallback method)."""
        self.logger.debug(f"Attempting to parse dependencies from {file_path.name} at: {file_path}")
        dependencies = {}
        try:
            # --- DEBUG: Read raw content ---
            raw_content = file_path.read_text(encoding='utf-8')
            self.logger.debug(f"Raw content read from {file_path.name} (first 500 chars): {raw_content[:500]}")
            # --- END DEBUG ---

            data = json.loads(raw_content) # Parse from raw content
            self.logger.debug(f"Successfully loaded JSON data from {file_path.name}")

            # --- DEBUG: Check top-level keys ---
            self.logger.debug(f"Top-level keys found: {list(data.keys())}")
            # --- END DEBUG ---

            # Include different dependency types
            for dep_type in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                self.logger.debug(f"Checking for dep_type: '{dep_type}'")
                dep_dict = data.get(dep_type) # Use .get() for safety

                # --- DEBUG: Check if dep_type exists and is a dict ---
                if dep_dict is None:
                     self.logger.debug(f"Dependency type '{dep_type}' not found in {file_path.name}.")
                     continue # Skip if this section doesn't exist
                if not isinstance(dep_dict, dict):
                     self.logger.warning(f"Dependency type '{dep_type}' in {file_path.name} is not a dictionary (found {type(dep_dict)}). Skipping.")
                     continue # Skip if it's not the expected format
                # --- END DEBUG ---

                self.logger.debug(f"Found {len(dep_dict)} items in '{dep_type}'. Iterating...")
                count = 0
                for package, version_range in dep_dict.items():
                    # --- DEBUG: Log each item found ---
                    self.logger.debug(f"  Processing item {count+1}: package='{package}', version_range='{version_range}'")
                    # --- END DEBUG ---
                    # Store the declared version range/specifier
                    dependencies[package] = str(version_range)
                    count += 1
                self.logger.debug(f"Finished iterating through '{dep_type}'. Processed {count} items.")

            self.logger.debug(f"Parsed {len(dependencies)} total dependency declarations from {file_path.name}")
            return dependencies
        except FileNotFoundError:
            self.logger.error(f"File not found during parsing attempt: {file_path}")
            raise ParsingError(f"File not found: {file_path.name}")
        except IOError as e:
            self.logger.error(f"IOError reading {file_path.name}: {str(e)}")
            raise ParsingError(f"Failed to read {file_path.name}: {str(e)}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {file_path.name}: {str(e)}")
            raise ParsingError(f"Invalid JSON in {file_path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing {file_path.name}: {str(e)}", exc_info=True)
            raise ParsingError(f"Unexpected error parsing {file_path.name}: {str(e)}")