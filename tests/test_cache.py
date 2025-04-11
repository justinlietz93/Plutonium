"""
Tests for the VersionCache.

This module contains unit tests for the VersionCache class,
which is responsible for caching package version information.
"""

import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path

from ..core.cache import VersionCache


class TestVersionCache:
    """Test cases for the VersionCache."""
    
    def test_init_new_cache(self):
        """Test initializing a new cache when the cache file doesn't exist."""
        # Mock Path.exists to return False (cache file doesn't exist)
        with patch('pathlib.Path.exists', return_value=False):
            cache = VersionCache()
            
            # Verify the cache is initialized as an empty dictionary
            assert cache.cache == {}
    
    def test_init_existing_cache(self):
        """Test initializing from an existing cache file."""
        # Sample cache data
        cache_data = {
            "npm:express": "4.17.1",
            "pypi:requests": "2.25.1"
        }
        
        # Mock Path.exists to return True (cache file exists)
        # Mock open to return the cached data
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(cache_data))):
            
            cache = VersionCache()
            
            # Verify the cache is loaded correctly
            assert cache.cache == cache_data
    
    def test_init_invalid_cache(self):
        """Test handling of invalid cache file."""
        # Mock Path.exists to return True (cache file exists)
        # Mock open to return invalid JSON
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="invalid json")), \
             patch('print') as mock_print:  # Mock print to avoid output during test
            
            cache = VersionCache()
            
            # Verify the cache is initialized as an empty dictionary on error
            assert cache.cache == {}
            
            # Verify error was printed
            mock_print.assert_called()
    
    def test_get_existing_key(self):
        """Test getting a value for an existing key."""
        # Create a cache with test data
        cache = VersionCache()
        cache.cache = {
            "npm:express": "4.17.1",
            "pypi:requests": "2.25.1"
        }
        
        # Get an existing key
        value = cache.get("npm:express")
        
        # Verify the correct value is returned
        assert value == "4.17.1"
    
    def test_get_nonexistent_key(self):
        """Test getting a value for a nonexistent key."""
        # Create an empty cache
        cache = VersionCache()
        
        # Get a nonexistent key
        value = cache.get("npm:nonexistent")
        
        # Verify None is returned
        assert value is None
    
    def test_set_new_key(self):
        """Test setting a value for a new key."""
        # Create a cache with test data
        cache = VersionCache()
        cache.cache = {
            "npm:express": "4.17.1"
        }
        
        # Mock the directory creation and file write
        with patch('os.makedirs') as mock_makedirs, \
             patch('builtins.open', mock_open()) as mock_file:
            
            # Set a new key
            cache.set("npm:react", "17.0.2")
            
            # Verify the cache was updated
            assert cache.cache["npm:react"] == "17.0.2"
            
            # Verify the cache was written to the file
            mock_makedirs.assert_called_once()
            mock_file.assert_called_once()
            mock_file().write.assert_called_once()
    
    def test_set_existing_key(self):
        """Test setting a value for an existing key."""
        # Create a cache with test data
        cache = VersionCache()
        cache.cache = {
            "npm:express": "4.17.1"
        }
        
        # Mock the directory creation and file write
        with patch('os.makedirs') as mock_makedirs, \
             patch('builtins.open', mock_open()) as mock_file:
            
            # Set an existing key with a new value
            cache.set("npm:express", "4.18.0")
            
            # Verify the cache was updated
            assert cache.cache["npm:express"] == "4.18.0"
            
            # Verify the cache was written to the file
            mock_makedirs.assert_called_once()
            mock_file.assert_called_once()
            mock_file().write.assert_called_once()
    
    def test_set_write_error(self):
        """Test handling of errors when writing to the cache file."""
        # Create a cache
        cache = VersionCache()
        
        # Mock the directory creation and file write with an error
        with patch('os.makedirs') as mock_makedirs, \
             patch('builtins.open', side_effect=IOError("Write error")), \
             patch('print') as mock_print:  # Mock print to avoid output during test
            
            # Set a key, which will trigger a write
            cache.set("npm:express", "4.17.1")
            
            # Verify the cache was still updated in memory
            assert cache.cache["npm:express"] == "4.17.1"
            
            # Verify error was printed
            mock_print.assert_called()
