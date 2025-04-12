"""
Maven dependency analyzer module.

This module provides functionality to analyze Maven dependencies
by parsing pom.xml files, fetching latest versions from Maven Central,
and checking vulnerabilities using the VulnCheck API.
"""

import logging
import requests
import xml.etree.ElementTree as ET
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


class MavenAnalyzer(IDependencyAnalyzer):
    """Analyzer for Maven dependencies."""

    # Maven POM XML namespace
    _NS = {"m": "http://maven.apache.org/POM/4.0.0"}

    def __init__(self, cache: Optional[VersionCache] = None, vulncheck_api_token: Optional[str] = None):
        """
        Initialize the MavenAnalyzer.

        Args:
            cache: Optional VersionCache instance.
            vulncheck_api_token: Optional VulnCheck API token.
        """
        super().__init__(cache) # Call parent __init__ if it exists and takes cache
        self.logger = logging.getLogger("analyzer.Maven")
        self.vulncheck_api_token = vulncheck_api_token
        self.vulncheck_headers = None
        if self.vulncheck_api_token:
            self.vulncheck_headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.vulncheck_api_token}'
            }
        else:
             self.logger.warning(
                 f"VulnCheck API token not provided to MavenAnalyzer. "
                 "Vulnerability information will not be fetched."
             )

    @property
    def environment_name(self) -> str:
        return "Maven"

    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Maven artifact from Maven Central Search API.

        Args:
            package_name: The package name in the format "groupId:artifactId"

        Returns:
            The latest version as a string or 'N/A' if lookup fails.

        Raises:
            NetworkError: If there's a network issue fetching the latest version.
            ParsingError: If the Maven Central response cannot be parsed.
            ValueError: If the package name format is invalid.
        """
        # Check cache first
        cached_version = self.cache.get(package_name)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version

        # Split package_name into groupId and artifactId
        try:
            group_id, artifact_id = package_name.split(':')
        except ValueError:
            self.logger.error(f"Invalid Maven package name format: {package_name}. Expected 'groupId:artifactId'.")
            raise ValueError(f"Invalid Maven package name format: {package_name}")

        # Fetch from Maven Central Search API
        # URL encode group_id and artifact_id just in case, though usually not needed
        encoded_group_id = urllib.parse.quote(group_id)
        encoded_artifact_id = urllib.parse.quote(artifact_id)
        url = API_URLS["Maven"].format(group_id=encoded_group_id, artifact_id=encoded_artifact_id)
        self.logger.debug(f"Fetching latest version for {package_name} from {url}")

        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status() # Raise HTTPError for bad responses
            data = response.json()

            # Check if docs were found
            if data.get("response", {}).get("numFound", 0) > 0:
                # Get version from the first doc ('v' field)
                latest_version = data["response"]["docs"][0].get("v")
                if latest_version:
                    self.cache.set(package_name, latest_version) # Cache successful lookups
                    return latest_version
                else:
                     self.logger.warning(f"Found artifact {package_name} but missing version field in response.")
                     return "N/A (Parse Error)"
            else:
                self.logger.warning(f"Artifact {package_name} not found on Maven Central.")
                return "N/A (Not Found)"

        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching latest version for {package_name} from Maven Central.")
            raise NetworkError(f"Timeout fetching latest version for {package_name} from Maven Central.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching latest version for {package_name} from Maven Central: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {package_name} from Maven Central: {str(e)}")
        except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"Error parsing Maven Central response for {package_name}: {str(e)}")
            raise ParsingError(f"Failed to parse latest version for {package_name} from Maven Central: {str(e)}")
        except Exception as e:
             self.logger.error(f"Unexpected error fetching latest version for {package_name}: {str(e)}", exc_info=True)
             return "N/A (Error)"


    def _fetch_vulnerabilities(self, group_id: str, artifact_id: str, version: str) -> List[str]:
        """
        Fetch vulnerabilities for a specific package version using VulnCheck API (PURL).

        Args:
            group_id: The Maven groupId.
            artifact_id: The Maven artifactId.
            version: The specific version of the package.

        Returns:
            A list of vulnerability IDs (e.g., CVEs) or an empty list if none found or error.
        """
        if not self.vulncheck_headers:
            self.logger.debug("Skipping vulnerability check: VulnCheck token not available.")
            return ["N/A (No Token)"]

        # Construct Package URL (PURL) for Maven
        # pkg:maven/groupId/artifactId@version
        # Encoding typically not needed for standard GAV coords, but apply if issues arise
        purl = f"pkg:maven/{group_id}/{artifact_id}@{version}"
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
        Analyze Maven dependencies defined in pom.xml.

        Args:
            directory: The directory containing the pom.xml file.

        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities).

        Raises:
            FileNotFoundError: If pom.xml doesn't exist.
            ParsingError: If pom.xml cannot be parsed.
            NetworkError: If latest versions cannot be fetched.
        """
        self.logger.info(f"Analyzing Maven dependencies in {directory}")

        pom_file_path = self._get_pom_xml_path(directory)
        # Returns dict mapping (groupId, artifactId) tuple to version string
        dependencies_in_pom = self._parse_pom(pom_file_path)

        results = []
        self.logger.info(f"Processing {len(dependencies_in_pom)} dependencies from {pom_file_path.name}")

        for (group_id, artifact_id), current_version in dependencies_in_pom.items():
            package_name = f"{group_id}:{artifact_id}" # Combine for reporting and latest version lookup
            latest_version = "Error"
            vulnerabilities = ["N/A"]

            is_variable_version = current_version.startswith("${") and current_version.endswith("}")

            try:
                # Get latest version regardless of current version format
                latest_version = self.get_latest_version(package_name)

                # Check vulnerabilities only if current_version is specific (not variable/unknown)
                if current_version not in ["unknown", "N/A"] and not is_variable_version:
                    vulnerabilities = self._fetch_vulnerabilities(group_id, artifact_id, current_version)
                elif is_variable_version:
                    vulnerabilities = ["N/A (Variable Version)"]
                else: # current_version is unknown or N/A
                    vulnerabilities = ["N/A (Unknown Version)"]

            except (NetworkError, ParsingError, ValueError, Exception) as e:
                self.logger.error(f"Error processing dependency {package_name}=={current_version}: {str(e)}")
                # Ensure latest_version reflects error state if it failed during lookup
                if latest_version != "Error" and isinstance(e, (NetworkError, ParsingError, ValueError)):
                     latest_version = "Error"
                vulnerabilities = ["Error (Processing)"]

            # Adjust current_version display for variables
            display_version = "(Variable)" if is_variable_version else current_version

            results.append((package_name, display_version, latest_version, vulnerabilities))

        self.logger.info(f"Finished processing Maven dependencies for {directory}. Found {len(results)} results.")
        return results


    def _get_pom_xml_path(self, directory: str) -> Path:
        """Get the path to the pom.xml file."""
        file_path = Path(directory) / "pom.xml"
        if not file_path.exists():
            self.logger.error(f"pom.xml not found in {directory}")
            raise FileNotFoundError(f"pom.xml not found in {directory}")
        return file_path


    def _find_text(self, element: Optional[ET.Element], tag: str) -> Optional[str]:
        """Helper to find text in an XML element, handling namespace."""
        if element is None:
            return None
        found = element.find(f"m:{tag}", self._NS)
        return found.text.strip() if found is not None and found.text else None

    def _parse_pom(self, file_path: Path) -> Dict[Tuple[str, str], str]:
        """
        Parse the pom.xml file and extract dependencies.

        Args:
            file_path: The path to the pom.xml file.

        Returns:
            A dictionary mapping (groupId, artifactId) tuples to their version strings.

        Raises:
            ParsingError: If there's an error parsing the pom.xml file.
        """
        self.logger.debug(f"Parsing dependencies from {file_path.name}")
        dependencies = {}
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # --- Basic Property Resolution (Optional but helpful) ---
            properties = {}
            props_element = root.find("m:properties", self._NS)
            if props_element is not None:
                for prop in props_element:
                    # Tag name without namespace prefix
                    tag_name = prop.tag.split('}', 1)[-1] if '}' in prop.tag else prop.tag
                    properties[tag_name] = prop.text.strip() if prop.text else ''
            # Add implicit properties
            properties['project.version'] = self._find_text(root, 'version') or \
                                            self._find_text(root.find('m:parent', self._NS), 'version') or ''
            properties['project.groupId'] = self._find_text(root, 'groupId') or \
                                            self._find_text(root.find('m:parent', self._NS), 'groupId') or ''
            # --- End Property Resolution ---


            # Find dependencies managed in dependencyManagement first
            managed_dependencies = {}
            dep_management = root.find("m:dependencyManagement/m:dependencies", self._NS)
            if dep_management is not None:
                 for dep in dep_management.findall("m:dependency", self._NS):
                     group_id = self._find_text(dep, "groupId")
                     artifact_id = self._find_text(dep, "artifactId")
                     version_raw = self._find_text(dep, "version")
                     if group_id and artifact_id and version_raw:
                          # Resolve properties in managed version
                          version = properties.get(version_raw[2:-1], version_raw) if version_raw.startswith('${') else version_raw
                          managed_dependencies[(group_id, artifact_id)] = version

            # Find actual dependencies
            deps_element = root.find("m:dependencies", self._NS)
            if deps_element is not None:
                 for dep in deps_element.findall("m:dependency", self._NS):
                     group_id = self._find_text(dep, "groupId")
                     artifact_id = self._find_text(dep, "artifactId")
                     version_raw = self._find_text(dep, "version") # Version might be missing or a property

                     if not group_id or not artifact_id:
                          self.logger.warning(f"Skipping dependency with missing groupId or artifactId in {file_path.name}")
                          continue

                     # Resolve version: Use direct version, then managed version, then 'unknown'
                     current_version = "unknown"
                     if version_raw:
                          # Resolve property if it's a variable like ${property.name}
                          if version_raw.startswith("${") and version_raw.endswith("}"):
                              prop_name = version_raw[2:-1]
                              resolved_prop = properties.get(prop_name)
                              if resolved_prop:
                                   current_version = resolved_prop
                              else:
                                   self.logger.warning(f"Could not resolve property '{version_raw}' for {group_id}:{artifact_id}")
                                   current_version = version_raw # Keep as variable string
                          else:
                              current_version = version_raw
                     elif (group_id, artifact_id) in managed_dependencies:
                          current_version = managed_dependencies[(group_id, artifact_id)]
                          self.logger.debug(f"Using managed version '{current_version}' for {group_id}:{artifact_id}")
                     else:
                          self.logger.warning(f"Version missing for dependency {group_id}:{artifact_id} and not found in dependencyManagement.")


                     key = (group_id, artifact_id)
                     dependencies[key] = current_version

            self.logger.debug(f"Parsed {len(dependencies)} dependencies from {file_path.name}")
            return dependencies
        except (IOError, ET.ParseError) as e:
            self.logger.error(f"Error parsing {file_path.name}: {str(e)}")
            raise ParsingError(f"Failed to parse {file_path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing {file_path.name}: {str(e)}", exc_info=True)
            raise ParsingError(f"Unexpected error parsing {file_path.name}: {str(e)}")