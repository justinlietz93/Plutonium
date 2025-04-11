"""
Cache module for storing and retrieving latest version information.

This module provides a simple caching mechanism to store and retrieve 
the latest versions of dependencies to reduce API calls.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional


class VersionCache:
    """A simple cache for storing the latest versions of dependencies."""
    
    def __init__(self, cache_file: str = "version_cache.json"):
        """Initialize the cache from the cache file or create an empty cache."""
        self.cache: Dict[str, str] = {}
        # Resolve cache file path relative to the executable (if running as PyInstaller bundle)
        if getattr(sys, 'frozen', False):  # Running as executable
            base_path = os.path.dirname(sys.executable)
        else:  # Running as script
            base_path = os.getcwd()
        print(f"Base path: {base_path}")  # Debug print
        self.cache_file = Path(base_path) / cache_file
        print(f"Using cache file: {self.cache_file}")  # Debug print
        
        try:
            print(f"Checking if cache file exists: {self.cache_file}")  # Debug print
            if self.cache_file.exists():
                print(f"Cache file exists, attempting to read")  # Debug print
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
            else:
                print("Cache file does not exist, starting with empty cache")
                self.cache = {}
        except (json.JSONDecodeError, IOError, Exception) as e:
            print(f"Error loading cache: {e}")
            self.cache = {}
    
    def get(self, package_key: str) -> Optional[str]:
        """
        Get the cached version for a package.
        
        Args:
            package_key: The key for the package (e.g., "npm:express", "pypi:requests")
            
        Returns:
            The cached version or None if not in cache
        """
        return self.cache.get(package_key)
    
    def set(self, package_key: str, version: str) -> None:
        """
        Set the cached version for a package and save the cache to disk.
        
        Args:
            package_key: The key for the package (e.g., "npm:express", "pypi:requests")
            version: The version to cache
        """
        self.cache[package_key] = version
        
        try:
            # Ensure the directory exists
            cache_dir = os.path.dirname(self.cache_file)
            if cache_dir:  # Only call makedirs if there's a directory component
                print(f"Creating directory: {cache_dir}")  # Debug print
                os.makedirs(cache_dir, exist_ok=True)
            else:
                print("No directory component in cache file path; skipping makedirs")
            
            # Verify write permissions
            print(f"Checking write permissions for directory: {cache_dir}")
            if not os.access(cache_dir, os.W_OK):
                raise PermissionError(f"No write permissions for directory: {cache_dir}")
            
            # Write the cache to the file
            print(f"Writing to cache file: {self.cache_file}")  # Debug print
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            print(f"Successfully wrote to cache file: {self.cache_file}")
        except (IOError, Exception) as e:
            print(f"Failed to write cache file {self.cache_file}: {e}")
            raise  # Re-raise to ensure the error is not swallowed