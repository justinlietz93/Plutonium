"""
Configuration validator module.

This module provides functionality to validate the dependency analyzer configuration
to ensure it contains all required fields with valid values.
"""

from pathlib import Path
from typing import Dict, Any, List

# Import from the constants module
from .constants import SUPPORTED_ENVIRONMENTS


class ConfigValidator:
    """Validates the dependency analyzer configuration."""
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> None:
        """
        Validate the dependency analyzer configuration.
        
        Args:
            config: The configuration dictionary to validate
            
        Raises:
            ValueError: If any validation check fails
        """
        # Check for required top-level keys
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")
            
        if "OutputFile" not in config:
            raise ValueError("Configuration missing required 'OutputFile' key")
        if not isinstance(config["OutputFile"], str):
            raise ValueError("'OutputFile' must be a string")
            
        if "Directories" not in config:
            raise ValueError("Configuration missing required 'Directories' key")
        if not isinstance(config["Directories"], list) or not config["Directories"]:
            raise ValueError("'Directories' must be a non-empty list")
            
        # Validate each directory entry
        for i, directory in enumerate(config["Directories"]):
            if not isinstance(directory, dict):
                raise ValueError(f"Directory at index {i} must be a dictionary")
                
            # Check for required keys in each directory entry
            if "Path" not in directory:
                raise ValueError(f"Directory at index {i} missing required 'Path' key")
            if not isinstance(directory["Path"], str):
                raise ValueError(f"'Path' at index {i} must be a string")
                
            # Verify the path exists
            dir_path = Path(directory["Path"])
            if not dir_path.exists():
                raise ValueError(f"Directory path '{dir_path}' does not exist")
            if not dir_path.is_dir():
                raise ValueError(f"Path '{dir_path}' is not a directory")
                
            # Check environments
            if "Environments" not in directory:
                raise ValueError(f"Directory at index {i} missing required 'Environments' key")
            if not isinstance(directory["Environments"], list) or not directory["Environments"]:
                raise ValueError(f"'Environments' at index {i} must be a non-empty list")
                
            # Verify each environment is supported
            for env in directory["Environments"]:
                if env not in SUPPORTED_ENVIRONMENTS:
                    supported_envs = ", ".join(SUPPORTED_ENVIRONMENTS)
                    raise ValueError(
                        f"Unsupported environment '{env}' at index {i}. "
                        f"Supported environments are: {supported_envs}"
                    )
