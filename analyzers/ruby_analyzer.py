"""
Ruby dependency analyzer module.

This module provides functionality to analyze Ruby dependencies
by parsing Gemfile.lock files, fetching latest versions from RubyGems.org,
and checking vulnerabilities using the VulnCheck API.
"""

import logging
import requests
import re # For parsing Gemfile.lock
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import json # For parsing JSON responses
import time # For potential rate limiting delays
import urllib.parse # Potentially for PURL encoding if needed
import os # For reading token env var

# Use relative imports within the package
from .interface import IDependencyAnalyzer
# Assuming constants are now in plutonium.core
from ..core.constants import API_URLS, DEFAULT_TIMEOUT, VULNCHECK_API_TOKEN_ENV_VAR
from ..core.exceptions import NetworkError, ParsingError, ConfigurationError
from ..core.cache import VersionCache


class RubyAnalyzer(IDependencyAnalyzer):
    """Analyzer for Ruby dependencies using Gemfile.lock."""

    # Regex to capture gem specs in Gemfile.lock
    _GEM_SPEC_RE = re.compile(r"^\s{4}([\w-]+)\s+\((.+)\)")

    def __init__(self, cache: Optional[VersionCache] = None, vulncheck_api_token: Optional[str] = None):
        """
        Initialize the RubyAnalyzer.

        Args:
            cache: Optional VersionCache instance.
            vulncheck_api_token: Optional VulnCheck API token.
        """
        super().__init__(cache)
        self.logger = logging.getLogger("analyzer.Ruby")
        self.vulncheck_api_token = vulncheck_api_token
        self.vulncheck_headers = None
        if self.vulncheck_api_token:
            self.vulncheck_headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.vulncheck_api_token}'
            }
        else:
             self.logger.warning(
                 f"VulnCheck API token not provided to RubyAnalyzer. "
                 "Vulnerability information will not be fetched."
             )

    @property
    def environment_name(self) -> str:
        return "Ruby"

    def get_latest_version(self, gem_name: str) -> str:
        """
        Get the latest version of a Ruby gem from RubyGems.org.

        Args:
            gem_name: The name of the gem.

        Returns:
            The latest version as a string or 'N/A' if lookup fails.

        Raises:
            NetworkError: If there's a network issue fetching the latest version.
            ParsingError: If the RubyGems response cannot be parsed.
        """
        # Check cache first
        cached_version = self.cache.get(gem_name)
        if cached_version:
            self.logger.debug(f"Cache hit for {gem_name}: {cached_version}")
            return cached_version

        # Fetch from RubyGems API
        # URL encoding usually not needed for gem names, but apply if required
        encoded_gem_name = urllib.parse.quote(gem_name)
        url = API_URLS["RubyGems"].format(gem_name=encoded_gem_name)
        self.logger.debug(f"Fetching latest version for {gem_name} from {url}")

        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 404:
                 self.logger.warning(f"Gem {gem_name} not found on RubyGems.org (404).")
                 return "N/A (Not Found)"
            response.raise_for_status() # Raise HTTPError for bad responses
            data = response.json()
            # The latest version is typically the 'version' field at the root
            latest_version = data.get("version")
            if latest_version:
                self.cache.set(gem_name, latest_version) # Cache successful lookups
                return latest_version
            else:
                self.logger.warning(f"Found gem {gem_name} but missing 'version' field in response.")
                return "N/A (Parse Error)"

        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching latest version for {gem_name} from RubyGems.")
            raise NetworkError(f"Timeout fetching latest version for {gem_name} from RubyGems.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching latest version for {gem_name} from RubyGems: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {gem_name} from RubyGems: {str(e)}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"Error parsing RubyGems response for {gem_name}: {str(e)}")
            raise ParsingError(f"Failed to parse latest version for {gem_name} from RubyGems: {str(e)}")
        except Exception as e:
             self.logger.error(f"Unexpected error fetching latest version for {gem_name}: {str(e)}", exc_info=True)
             return "N/A (Error)"


    def _fetch_vulnerabilities(self, gem_name: str, version: str) -> List[str]:
        """
        Fetch vulnerabilities for a specific gem version using VulnCheck API (PURL).

        Args:
            gem_name: The name of the gem.
            version: The specific version of the gem.

        Returns:
            A list of vulnerability IDs (e.g., CVEs) or an empty list if none found or error.
        """
        if not self.vulncheck_headers:
            self.logger.debug("Skipping vulnerability check: VulnCheck token not available.")
            return ["N/A (No Token)"]

        # Construct Package URL (PURL) for RubyGems
        # pkg:gem/gem-name@version
        purl = f"pkg:gem/{gem_name}@{version}"
        url = API_URLS["VulnCheck_PURL"]
        params = {'purl': purl}

        self.logger.debug(f"Fetching vulnerabilities for {purl} from {url}")
        try:
            # Implement basic rate limiting delay if needed
            # time.sleep(0.1)

            response = requests.get(url, headers=self.vulncheck_headers, params=params, timeout=DEFAULT_TIMEOUT)

            if response.status_code == 401:
                 self.logger.error(f"VulnCheck API Error 401: Unauthorized. Check your API token.")
                 return ["Error (Unauthorized)"]
            if response.status_code == 403:
                 self.logger.error(f"VulnCheck API Error 403: Forbidden. Check permissions or rate limits.")
                 return ["Error (Forbidden)"]
            if response.status_code == 404:
                 self.logger.debug(f"No vulnerability data found for {purl} (404).")
                 return []
            if response.status_code == 429:
                 self.logger.warning(f"VulnCheck API Error 429: Rate limit exceeded for {purl}. Consider adding delays.")
                 return ["Error (Rate Limit)"]

            response.raise_for_status()

            data = response.json()
            vulnerabilities = []
            if isinstance(data, list):
                 for vuln in data:
                      if isinstance(vuln, dict) and 'id' in vuln:
                           vulnerabilities.append(vuln['id'])
            elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                 for vuln in data['data']:
                     if isinstance(vuln, dict) and 'id' in vuln:
                          vulnerabilities.append(vuln['id'])
            else:
                self.logger.warning(f"Unexpected VulnCheck API response format for {purl}: {data}")

            self.logger.debug(f"Found {len(vulnerabilities)} vulnerabilities for {purl}")
            return vulnerabilities if vulnerabilities else []

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
        Analyze Ruby dependencies defined in Gemfile.lock.

        Args:
            directory: The directory containing the Gemfile.lock file.

        Returns:
            A list of tuples (gem_name, current_version, latest_version, vulnerabilities).

        Raises:
            FileNotFoundError: If Gemfile.lock doesn't exist.
            ParsingError: If Gemfile.lock cannot be parsed.
            NetworkError: If latest versions cannot be fetched.
        """
        self.logger.info(f"Analyzing Ruby dependencies in {directory}")

        lock_file_path = self._get_lockfile_path(directory)
        dependencies_in_lockfile = self._parse_gemfile_lock(lock_file_path)

        results = []
        self.logger.info(f"Processing {len(dependencies_in_lockfile)} dependencies from {lock_file_path.name}")

        for gem_name, current_version in dependencies_in_lockfile.items():
            latest_version = "Error"
            vulnerabilities = ["N/A"]
            try:
                latest_version = self.get_latest_version(gem_name)
                if latest_version not in ["N/A (Not Found)", "N/A (Parse Error)", "N/A (Error)"]:
                     vulnerabilities = self._fetch_vulnerabilities(gem_name, current_version)
                else:
                     vulnerabilities = ["N/A (Version Lookup Failed)"]

            except (NetworkError, ParsingError, ValueError, Exception) as e:
                self.logger.error(f"Error processing dependency {gem_name}=={current_version}: {str(e)}")
                if latest_version != "Error" and isinstance(e, (NetworkError, ParsingError, ValueError)):
                    latest_version = "Error"
                vulnerabilities = ["Error (Processing)"]

            results.append((gem_name, current_version, latest_version, vulnerabilities))

        self.logger.info(f"Finished processing Ruby dependencies for {directory}. Found {len(results)} results.")
        return results

    def _get_lockfile_path(self, directory: str) -> Path:
        """Get the path to the Gemfile.lock file."""
        file_path = Path(directory) / "Gemfile.lock"
        if not file_path.exists():
            self.logger.error(f"Gemfile.lock not found in {directory}")
            raise FileNotFoundError(f"Gemfile.lock not found in {directory}")
        return file_path

    def _parse_gemfile_lock(self, lock_file_path: Path) -> Dict[str, str]:
        """
        Parse the Gemfile.lock file to extract exact gem versions.

        Args:
            lock_file_path: Path to the Gemfile.lock file.

        Returns:
            Dictionary mapping gem names to their exact versions.

        Raises:
            ParsingError: If the file cannot be read or parsed.
        """
        self.logger.debug(f"Parsing dependencies from {lock_file_path.name}")
        dependencies = {}
        in_specs_section = False
        try:
            with open(lock_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip() # Keep leading whitespace

                    if line == "GEM":
                        in_specs_section = False # Reset if GEM section encountered again
                    elif line.strip() == "specs:":
                        in_specs_section = True
                        continue # Move to the next line after finding specs:

                    if in_specs_section:
                        # Check if the line matches the spec format "    gem-name (version)"
                        match = self._GEM_SPEC_RE.match(line)
                        if match:
                            gem_name = match.group(1)
                            version = match.group(2)
                            # Handle potential platform specific versions like "1.2.3-x86_64-linux"
                            version = version.split('-')[0]
                            dependencies[gem_name] = version
                        elif line.strip() == "":
                             # Blank line might indicate end of specs or just spacing
                             # If we encounter a non-indented line later, we should stop
                             pass
                        elif not line.startswith(" "):
                             # If we hit a line that's not indented, assume specs section ended
                             in_specs_section = False

            self.logger.debug(f"Parsed {len(dependencies)} dependencies from {lock_file_path.name}")
            if not dependencies:
                 self.logger.warning(f"No dependencies found in the 'specs:' section of {lock_file_path.name}. Check file format.")
            return dependencies
        except IOError as e:
            self.logger.error(f"Error reading {lock_file_path.name}: {str(e)}")
            raise ParsingError(f"Failed to read {lock_file_path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing {lock_file_path.name}: {str(e)}", exc_info=True)
            raise ParsingError(f"Unexpected error parsing {lock_file_path.name}: {str(e)}")