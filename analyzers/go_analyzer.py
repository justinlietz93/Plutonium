"""
Go dependency analyzer module.

This module provides functionality to analyze Go dependencies
by parsing go.mod files, fetching latest versions from the Go proxy,
and checking vulnerabilities using the VulnCheck API.
"""

import logging
import requests
import re # For parsing go.mod
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import json # For parsing JSON API responses
import time # For potential rate limiting delays
import urllib.parse # For PURL encoding if needed
import os # For reading token env var

# Use relative imports within the package
from .interface import IDependencyAnalyzer
# Assuming constants are now in plutonium.core
from ..core.constants import API_URLS, DEFAULT_TIMEOUT, VULNCHECK_API_TOKEN_ENV_VAR
from ..core.exceptions import NetworkError, ParsingError, ConfigurationError
from ..core.cache import VersionCache


class GoAnalyzer(IDependencyAnalyzer):
    """Analyzer for Go dependencies using go.mod."""

    def __init__(self, cache: Optional[VersionCache] = None, vulncheck_api_token: Optional[str] = None):
        """
        Initialize the GoAnalyzer.

        Args:
            cache: Optional VersionCache instance.
            vulncheck_api_token: Optional VulnCheck API token.
        """
        super().__init__(cache)
        self.logger = logging.getLogger("analyzer.Go")
        self.vulncheck_api_token = vulncheck_api_token
        self.vulncheck_headers = None
        if self.vulncheck_api_token:
            self.vulncheck_headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.vulncheck_api_token}'
            }
        else:
             self.logger.warning(
                 f"VulnCheck API token not provided to GoAnalyzer. "
                 "Vulnerability information will not be fetched."
             )

    @property
    def environment_name(self) -> str:
        return "Go"

    def _encode_go_module_path(self, module_path: str) -> str:
         """Encode Go module path according to proxy requirements (case encoding)."""
         # Ref: https://go.dev/ref/mod#goproxy-protocol
         # Go module paths are case-sensitive, but some parts might need escaping
         # if they contain uppercase letters or certain symbols for the proxy URL.
         # The proxy expects '!'-escaped uppercase letters.
         # For simplicity here, we'll just use standard URL quoting,
         # which might work for most common cases with proxy.golang.org.
         # A more accurate implementation would replace A-Z with !a-!z.
         return urllib.parse.quote(module_path)

    def get_latest_version(self, module_path: str) -> str:
        """
        Get the latest version of a Go module from the Go proxy.

        Note: This fetches the list of versions and returns the last one,
        which might not always be the true latest stable release according
        to semantic versioning (could be a pre-release).

        Args:
            module_path: The Go module path (e.g., "github.com/gin-gonic/gin").

        Returns:
            The latest version string found or 'N/A' if lookup fails.

        Raises:
            NetworkError: If there's a network issue fetching the version list.
            ParsingError: If the Go proxy response cannot be parsed.
        """
        # Check cache first
        cached_version = self.cache.get(module_path)
        if cached_version:
            self.logger.debug(f"Cache hit for {module_path}: {cached_version}")
            return cached_version

        # Fetch version list from Go proxy
        encoded_module_path = self._encode_go_module_path(module_path)
        url = API_URLS["Go"].format(package=encoded_module_path)
        self.logger.debug(f"Fetching version list for {module_path} from {url}")

        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            # Go proxy returns 404 or 410 Gone for modules not found
            if response.status_code in [404, 410]:
                 self.logger.warning(f"Module {module_path} not found on Go proxy {url} ({response.status_code}).")
                 return "N/A (Not Found)"
            response.raise_for_status() # Raise HTTPError for other bad responses

            versions = response.text.strip().split('\n')
            if not versions or not versions[-1]:
                 self.logger.warning(f"No valid versions found in Go proxy response for {module_path}.")
                 return "N/A (No Versions)"

            # Take the last version listed (simplistic approach)
            latest_version = versions[-1].strip()
            self.cache.set(module_path, latest_version) # Cache successful lookups
            return latest_version

        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching version list for {module_path} from Go proxy.")
            raise NetworkError(f"Timeout fetching version list for {module_path} from Go proxy.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching version list for {module_path} from Go proxy: {str(e)}")
            raise NetworkError(f"Failed to fetch version list for {module_path} from Go proxy: {str(e)}")
        except (IndexError, ValueError) as e: # ValueError for potential strip/split issues
            self.logger.error(f"Error parsing Go proxy response for {module_path}: {str(e)}")
            raise ParsingError(f"Failed to parse version list for {module_path} from Go proxy: {str(e)}")
        except Exception as e:
             self.logger.error(f"Unexpected error fetching latest version for {module_path}: {str(e)}", exc_info=True)
             return "N/A (Error)"


    def _fetch_vulnerabilities(self, module_path: str, version: str) -> List[str]:
        """
        Fetch vulnerabilities for a specific module version using VulnCheck API (PURL).

        Args:
            module_path: The Go module path.
            version: The specific version of the module (e.g., "v1.2.3").

        Returns:
            A list of vulnerability IDs (e.g., CVEs) or an empty list if none found or error.
        """
        if not self.vulncheck_headers:
            self.logger.debug("Skipping vulnerability check: VulnCheck token not available.")
            return ["N/A (No Token)"]

        # Construct Package URL (PURL) for Go
        # Format: pkg:golang/module/path@version (without leading 'v')
        purl_version = version.lstrip('v') # Remove leading 'v' if present
        # Encoding usually not needed for module path in PURL, but good practice
        encoded_module_path = urllib.parse.quote(module_path)
        purl = f"pkg:golang/{encoded_module_path}@{purl_version}"
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
        Analyze Go dependencies defined in go.mod.

        Args:
            directory: The directory containing the go.mod file.

        Returns:
            A list of tuples (module_path, current_version, latest_version, vulnerabilities).

        Raises:
            FileNotFoundError: If go.mod doesn't exist.
            ParsingError: If go.mod cannot be parsed.
            NetworkError: If latest versions cannot be fetched.
        """
        self.logger.info(f"Analyzing Go dependencies in {directory}")

        mod_file_path = self._get_mod_file_path(directory)
        # Note: Versions in go.mod are minimum requirements
        dependencies_in_mod = self._parse_go_mod(mod_file_path)

        results = []
        self.logger.info(f"Processing {len(dependencies_in_mod)} dependencies from {mod_file_path.name}")

        for module_path, current_version in dependencies_in_mod.items():
            # Skip indirect dependencies often marked with // indirect
            if current_version.endswith("// indirect"):
                 self.logger.debug(f"Skipping indirect dependency: {module_path}")
                 continue

            latest_version = "Error"
            vulnerabilities = ["N/A"]
            try:
                latest_version = self.get_latest_version(module_path)
                # Version check needs to be careful with pseudo-versions (v0.0.0-...)
                # We fetch vulns based on the version specified in go.mod
                vulnerabilities = self._fetch_vulnerabilities(module_path, current_version)

            except (NetworkError, ParsingError, ValueError, Exception) as e:
                self.logger.error(f"Error processing dependency {module_path} @ {current_version}: {str(e)}")
                if latest_version != "Error" and isinstance(e, (NetworkError, ParsingError, ValueError)):
                    latest_version = "Error"
                vulnerabilities = ["Error (Processing)"]

            results.append((module_path, current_version, latest_version, vulnerabilities))

        self.logger.info(f"Finished processing Go dependencies for {directory}. Found {len(results)} direct results.")
        return results

    def _get_mod_file_path(self, directory: str) -> Path:
        """Get the path to the go.mod file."""
        file_path = Path(directory) / "go.mod"
        if not file_path.exists():
            self.logger.error(f"go.mod not found in {directory}")
            raise FileNotFoundError(f"go.mod not found in {directory}")
        return file_path

    def _parse_go_mod(self, file_path: Path) -> Dict[str, str]:
        """
        Parse the go.mod file and extract direct dependencies from require blocks.

        Args:
            file_path: The path to the go.mod file.

        Returns:
            A dictionary mapping module paths to their version strings (as listed in go.mod).

        Raises:
            ParsingError: If there's an error parsing the go.mod file.
        """
        self.logger.debug(f"Parsing dependencies from {file_path.name}")
        dependencies = {}
        # Regex to capture module path and version, potentially with // indirect comment
        # Allows versions like v1.2.3, v0.0.0-timestamp-commit, v1.2.3+incompatible
        require_pattern = re.compile(r"^\s*([^\s]+)\s+(v[0-9]+\.[0-9]+\.[0-9]+(?:-[\w\.\+]+)?(?:[\+\.][\w]+)?(?:[\w\.\-\+]+)?)(?:\s*//\s*indirect)?\s*$")

        in_require_block = False
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith(('//', 'module ', 'go ', 'exclude ', 'replace ')):
                    continue

                if stripped_line == "require (":
                    in_require_block = True
                    continue
                if stripped_line == ")":
                    in_require_block = False
                    continue

                target_line = None
                if stripped_line.startswith("require "):
                    # Single line require: remove "require " prefix before matching
                    target_line = stripped_line[len("require "):].strip()
                elif in_require_block:
                    # Inside require block: match the whole stripped line
                    target_line = stripped_line

                if target_line:
                    match = require_pattern.match(target_line)
                    if match:
                        module_path = match.group(1)
                        version = match.group(2)
                        # Check for // indirect comment which might not be captured by regex end $ if present later
                        comment_pos = line.find('// indirect') # Check original line for comment
                        is_indirect = comment_pos != -1

                        # Store version, maybe mark indirect ones if needed later
                        # For now, let analyze_dependencies skip them
                        dependencies[module_path] = version + (" // indirect" if is_indirect else "")

                    elif in_require_block or stripped_line.startswith("require "):
                         # Line likely contains a module but didn't match regex (e.g., complex replace?)
                         self.logger.warning(f"Could not parse require line {line_num} in {file_path.name}: '{line.strip()}'")


            self.logger.debug(f"Parsed {len(dependencies)} require entries from {file_path.name}")
            return dependencies
        except IOError as e:
            self.logger.error(f"Error reading {file_path.name}: {str(e)}")
            raise ParsingError(f"Failed to read {file_path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing {file_path.name}: {str(e)}", exc_info=True)
            raise ParsingError(f"Unexpected error parsing {file_path.name}: {str(e)}")