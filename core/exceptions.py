"""
Exceptions module for the dependency analyzer.

This module defines custom exception classes and error handling utilities
for the dependency analyzer application.
"""

import subprocess
import logging
from typing import List, Optional


class DependencyAnalyzerError(Exception):
    """Base exception class for all dependency analyzer errors."""
    pass


class ConfigurationError(DependencyAnalyzerError):
    """Exception raised for configuration-related errors."""
    pass


class CommandExecutionError(DependencyAnalyzerError):
    """Exception raised when a command execution fails."""
    pass


class NetworkError(DependencyAnalyzerError):
    """Exception raised for network-related errors."""
    pass


class ParsingError(DependencyAnalyzerError):
    """Exception raised when parsing dependency files fails."""
    pass


def run_command(command: List[str], cwd: Optional[str] = None, timeout: Optional[int] = None) -> str:
    """
    Run a shell command and return its output.
    
    Args:
        command: List of command and arguments to execute
        cwd: Working directory in which to execute the command
        timeout: Timeout in seconds for the command execution
        
    Returns:
        The standard output of the command as a string
        
    Raises:
        FileNotFoundError: If the command executable is not found
        CommandExecutionError: If the command returns a non-zero exit code
    """
    try:
        # Run the command and capture output
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,  # Don't raise exception on non-zero exit code, we'll handle it
            timeout=timeout
        )
        
        # Check if the command was successful
        if result.returncode != 0:
            error_msg = (
                f"Command '{' '.join(command)}' failed with exit code {result.returncode}.\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )
            raise CommandExecutionError(error_msg)
        
        return result.stdout
    
    except FileNotFoundError as e:
        # Command executable not found
        raise FileNotFoundError(f"Command not found: {command[0]}") from e
    
    except subprocess.TimeoutExpired as e:
        # Command timed out
        raise CommandExecutionError(f"Command timed out after {timeout} seconds: {' '.join(command)}") from e
    
    except Exception as e:
        # Any other exception
        raise CommandExecutionError(f"Error executing command '{' '.join(command)}': {str(e)}") from e
