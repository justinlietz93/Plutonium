"""
Tests for the ConfigValidator.

This module contains unit tests for the ConfigValidator class,
which is responsible for validating the configuration for the dependency analyzer.
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from ..core.config_validator import ConfigValidator
from ..core.constants import SUPPORTED_ENVIRONMENTS


class TestConfigValidator:
    """Test cases for the ConfigValidator."""
    
    @pytest.fixture
    def valid_config(self):
        """Create a valid configuration dictionary."""
        return {
            "OutputFile": "test_report.md",
            "Directories": [
                {
                    "Path": "/test/dir1",
                    "Environments": ["Node.js", "Python"]
                },
                {
                    "Path": "/test/dir2",
                    "Environments": ["Ruby"]
                }
            ]
        }
    
    def test_validate_valid_config(self, valid_config):
        """Test validating a valid configuration."""
        # Mock Path.exists to return True for all paths
        with patch('pathlib.Path.exists', return_value=True):
            # This should not raise an exception
            ConfigValidator.validate(valid_config)
    
    def test_validate_not_dict(self):
        """Test validating a non-dictionary configuration."""
        with pytest.raises(ValueError, match="Configuration must be a dictionary"):
            ConfigValidator.validate("not a dict")
    
    def test_validate_missing_output_file(self, valid_config):
        """Test validating a configuration with a missing OutputFile."""
        config = valid_config.copy()
        del config["OutputFile"]
        
        with pytest.raises(ValueError, match="missing required 'OutputFile' key"):
            ConfigValidator.validate(config)
    
    def test_validate_invalid_output_file_type(self, valid_config):
        """Test validating a configuration with an invalid OutputFile type."""
        config = valid_config.copy()
        config["OutputFile"] = 123  # Not a string
        
        with pytest.raises(ValueError, match="'OutputFile' must be a string"):
            ConfigValidator.validate(config)
    
    def test_validate_missing_directories(self, valid_config):
        """Test validating a configuration with missing Directories."""
        config = valid_config.copy()
        del config["Directories"]
        
        with pytest.raises(ValueError, match="missing required 'Directories' key"):
            ConfigValidator.validate(config)
    
    def test_validate_empty_directories(self, valid_config):
        """Test validating a configuration with empty Directories."""
        config = valid_config.copy()
        config["Directories"] = []
        
        with pytest.raises(ValueError, match="'Directories' must be a non-empty list"):
            ConfigValidator.validate(config)
    
    def test_validate_invalid_directories_type(self, valid_config):
        """Test validating a configuration with an invalid Directories type."""
        config = valid_config.copy()
        config["Directories"] = "not a list"
        
        with pytest.raises(ValueError, match="'Directories' must be a non-empty list"):
            ConfigValidator.validate(config)
    
    def test_validate_directory_not_dict(self, valid_config):
        """Test validating a configuration with a directory that's not a dictionary."""
        config = valid_config.copy()
        config["Directories"] = ["not a dict"]
        
        with pytest.raises(ValueError, match="Directory at index 0 must be a dictionary"):
            ConfigValidator.validate(config)
    
    def test_validate_directory_missing_path(self, valid_config):
        """Test validating a configuration with a directory missing a Path."""
        config = valid_config.copy()
        config["Directories"][0] = {
            "Environments": ["Node.js"]
        }
        
        with pytest.raises(ValueError, match="Directory at index 0 missing required 'Path' key"):
            ConfigValidator.validate(config)
    
    def test_validate_directory_invalid_path_type(self, valid_config):
        """Test validating a configuration with a directory with an invalid Path type."""
        config = valid_config.copy()
        config["Directories"][0]["Path"] = 123  # Not a string
        
        with pytest.raises(ValueError, match="'Path' at index 0 must be a string"):
            ConfigValidator.validate(config)
    
    def test_validate_directory_path_not_exist(self, valid_config):
        """Test validating a configuration with a directory path that doesn't exist."""
        # Mock Path.exists to return False for the first path
        def mock_exists(path):
            return "/test/dir1" not in str(path)
        
        with patch('pathlib.Path.exists', side_effect=mock_exists):
            with pytest.raises(ValueError, match="Directory path '.+' does not exist"):
                ConfigValidator.validate(valid_config)
    
    def test_validate_directory_missing_environments(self, valid_config):
        """Test validating a configuration with a directory missing Environments."""
        config = valid_config.copy()
        config["Directories"][0] = {
            "Path": "/test/dir1"
        }
        
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ValueError, match="Directory at index 0 missing required 'Environments' key"):
                ConfigValidator.validate(config)
    
    def test_validate_directory_empty_environments(self, valid_config):
        """Test validating a configuration with a directory with empty Environments."""
        config = valid_config.copy()
        config["Directories"][0]["Environments"] = []
        
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ValueError, match="'Environments' at index 0 must be a non-empty list"):
                ConfigValidator.validate(config)
    
    def test_validate_directory_invalid_environments_type(self, valid_config):
        """Test validating a configuration with a directory with an invalid Environments type."""
        config = valid_config.copy()
        config["Directories"][0]["Environments"] = "not a list"
        
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ValueError, match="'Environments' at index 0 must be a non-empty list"):
                ConfigValidator.validate(config)
    
    def test_validate_directory_unsupported_environment(self, valid_config):
        """Test validating a configuration with a directory with an unsupported environment."""
        config = valid_config.copy()
        config["Directories"][0]["Environments"] = ["UnsupportedEnv"]
        
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ValueError, match="Unsupported environment 'UnsupportedEnv'"):
                ConfigValidator.validate(config)
