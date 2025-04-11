"""
Tests for the custom exceptions and helper functions.

This module contains unit tests for the custom exception classes and
helper functions defined in the exceptions module.
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock

from ..core.exceptions import (
    DependencyAnalyzerError,
    ConfigurationError,
    CommandExecutionError,
    NetworkError,
    ParsingError,
    run_command
)


class TestCustomExceptions:
    """Test cases for the custom exception classes."""
    
    def test_dependency_analyzer_error(self):
        """Test the DependencyAnalyzerError exception."""
        # Verify that it inherits from Exception
        assert issubclass(DependencyAnalyzerError, Exception)
        
        # Create an instance and verify the message
        error = DependencyAnalyzerError("Test error message")
        assert str(error) == "Test error message"
    
    def test_configuration_error(self):
        """Test the ConfigurationError exception."""
        # Verify that it inherits from DependencyAnalyzerError
        assert issubclass(ConfigurationError, DependencyAnalyzerError)
        
        # Create an instance and verify the message
        error = ConfigurationError("Invalid configuration")
        assert str(error) == "Invalid configuration"
    
    def test_command_execution_error(self):
        """Test the CommandExecutionError exception."""
        # Verify that it inherits from DependencyAnalyzerError
        assert issubclass(CommandExecutionError, DependencyAnalyzerError)
        
        # Create an instance and verify the message
        error = CommandExecutionError("Command failed")
        assert str(error) == "Command failed"
    
    def test_network_error(self):
        """Test the NetworkError exception."""
        # Verify that it inherits from DependencyAnalyzerError
        assert issubclass(NetworkError, DependencyAnalyzerError)
        
        # Create an instance and verify the message
        error = NetworkError("Network request failed")
        assert str(error) == "Network request failed"
    
    def test_parsing_error(self):
        """Test the ParsingError exception."""
        # Verify that it inherits from DependencyAnalyzerError
        assert issubclass(ParsingError, DependencyAnalyzerError)
        
        # Create an instance and verify the message
        error = ParsingError("Failed to parse file")
        assert str(error) == "Failed to parse file"


class TestRunCommand:
    """Test cases for the run_command helper function."""
    
    def test_run_command_success(self):
        """Test running a command that succeeds."""
        # Mock subprocess.run to return a successful result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Command output"
        
        with patch('subprocess.run', return_value=mock_result):
            output = run_command(["echo", "test"])
            
            # Verify the command output is returned
            assert output == "Command output"
    
    def test_run_command_failure(self):
        """Test running a command that fails."""
        # Mock subprocess.run to return a failed result
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "stdout output"
        mock_result.stderr = "stderr output"
        
        with patch('subprocess.run', return_value=mock_result):
            # Verify CommandExecutionError is raised
            with pytest.raises(CommandExecutionError) as excinfo:
                run_command(["failing", "command"])
            
            # Check that the error message includes the command, return code, stdout, and stderr
            error_message = str(excinfo.value)
            assert "failing command" in error_message
            assert "exit code 1" in error_message
            assert "stdout output" in error_message
            assert "stderr output" in error_message
    
    def test_run_command_command_not_found(self):
        """Test running a command that doesn't exist."""
        # Mock subprocess.run to raise FileNotFoundError
        with patch('subprocess.run', side_effect=FileNotFoundError("Command not found")):
            # Verify FileNotFoundError is raised
            with pytest.raises(FileNotFoundError) as excinfo:
                run_command(["nonexistent", "command"])
            
            # Check that the error message includes the command
            error_message = str(excinfo.value)
            assert "Command not found: nonexistent" in error_message
    
    def test_run_command_timeout(self):
        """Test running a command that times out."""
        # Mock subprocess.run to raise TimeoutExpired
        timeout_error = subprocess.TimeoutExpired(cmd=["long", "command"], timeout=10)
        
        with patch('subprocess.run', side_effect=timeout_error):
            # Verify CommandExecutionError is raised
            with pytest.raises(CommandExecutionError) as excinfo:
                run_command(["long", "command"], timeout=10)
            
            # Check that the error message includes the command and timeout
            error_message = str(excinfo.value)
            assert "long command" in error_message
            assert "timed out after 10 seconds" in error_message
    
    def test_run_command_other_error(self):
        """Test running a command that raises some other exception."""
        # Mock subprocess.run to raise a generic exception
        with patch('subprocess.run', side_effect=Exception("Some other error")):
            # Verify CommandExecutionError is raised
            with pytest.raises(CommandExecutionError) as excinfo:
                run_command(["command"])
            
            # Check that the error message includes the command and the original error
            error_message = str(excinfo.value)
            assert "command" in error_message
            assert "Some other error" in error_message
