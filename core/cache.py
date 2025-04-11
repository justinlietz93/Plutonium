"""
Cache module for storing and retrieving latest version information.

This module provides a simple caching mechanism to store and retrieve 
the latest versions of dependencies to reduce API calls.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional


class VersionCache:
    """A simple cache for storing the latest versions of dependencies."""
    
    # Cache file path
    CACHE_FILE = Path("version_cache.json")
    
    def __init__(self):
        """Initialize the cache from the cache file or create an empty cache."""
        self.cache: Dict[str, str] = {}
        
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r') as f:
                    self.cache = json.load(f)
        except (json.JSONDecodeError, IOError, Exception) as e:
            # If there's an error reading the cache, start with an empty cache
            self.cache = {}
            # In a real application, we might want to log this error
            print(f"Error loading cache: {e}")
    
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
            os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
            
            # Write the cache to the file
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except (IOError, Exception) as e:
            # In a real application, we would log this error
            print(f"Error saving cache: {e}")
