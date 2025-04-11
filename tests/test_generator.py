"""
Tests for the DependencyReportGenerator.

This module contains unit tests for the DependencyReportGenerator class,
which is responsible for orchestrating the dependency analysis process.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path
from io import StringIO

from ..core.generator import DependencyReportGenerator
from ..core.config_validator import ConfigValidator
from ..core.factory import DependencyAnalyzerFactory
from ..analyzers.interface import IDependencyAnalyzer
from ..core.exceptions import DependencyAnalyzerError, ConfigurationError


class TestDependencyReportGenerator:
    """Test cases for the DependencyReportGenerator."""
    
    @pytest.fixture
    def mock_analyzer(self):
        """Create a mock analyzer for testing."""
        mock = MagicMock(spec=IDependencyAnalyzer)
        mock.environment_name = "MockEnvironment"
        mock.analyze_dependencies = MagicMock()
        return mock
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration dictionary."""
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
    
    def test_generate_report_success(self, mock_analyzer, sample_config):
        """Test successful report generation."""
        # Mock file operations
        m_open = mock_open()
        
        # Set up our mocks
        with patch("builtins.open", m_open), \
             patch("json.load", return_value=sample_config), \
             patch.object(ConfigValidator, "validate"), \
             patch.object(DependencyAnalyzerFactory, "create_analyzers", 
                         return_value=[mock_analyzer]), \
             patch("pathlib.Path.exists", return_value=True):
            
            # Create and run the generator
            generator = DependencyReportGenerator()
            generator.generate_report("test_config.json")
            
            # Verify config validation was called
            ConfigValidator.validate.assert_called_once_with(sample_config)
            
            # Verify analyzers were created for each directory
            assert DependencyAnalyzerFactory.create_analyzers.call_count == len(sample_config["Directories"])
            
            # Verify analyze_dependencies was called for each analyzer
            assert mock_analyzer.analyze_dependencies.call_count == len(sample_config["Directories"])
            
            # Verify the report file was opened for writing
            m_open.assert_any_call(sample_config["OutputFile"], "w", encoding="utf-8")
            
            # Verify report file was opened for writing final footer
            m_open.assert_any_call(sample_config["OutputFile"], "a", encoding="utf-8")
    
    def test_generate_report_config_error(self):
        """Test handling of configuration errors."""
        # Mock file operations with error
        with patch("builtins.open", side_effect=IOError("File not found")):
            
            # Create generator
            generator = DependencyReportGenerator()
            
            # Test that the correct exception is raised
            with pytest.raises(ConfigurationError):
                generator.generate_report("nonexistent_config.json")
    
    def test_generate_report_validation_error(self, sample_config):
        """Test handling of configuration validation errors."""
        # Mock validation to raise error
        validation_error = ValueError("Invalid configuration")
        
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_config))), \
             patch("json.load", return_value=sample_config), \
             patch.object(ConfigValidator, "validate", side_effect=validation_error):
            
            # Create generator
            generator = DependencyReportGenerator()
            
            # Test that the correct exception is propagated
            with pytest.raises(ValueError) as exc_info:
                generator.generate_report("test_config.json")
            
            assert str(exc_info.value) == str(validation_error)
    
    def test_generate_report_analyzer_error(self, mock_analyzer, sample_config):
        """Test handling of analyzer errors."""
        # Make the analyzer raise an exception
        mock_analyzer.analyze_dependencies.side_effect = Exception("Analyzer error")
        
        # Mock file operations
        m_open = mock_open()
        
        with patch("builtins.open", m_open), \
             patch("json.load", return_value=sample_config), \
             patch.object(ConfigValidator, "validate"), \
             patch.object(DependencyAnalyzerFactory, "create_analyzers", 
                         return_value=[mock_analyzer]), \
             patch("pathlib.Path.exists", return_value=True):
            
            # Create and run the generator
            generator = DependencyReportGenerator()
            generator.generate_report("test_config.json")
            
            # Verify the error was handled (no exception raised)
            assert mock_analyzer.analyze_dependencies.call_count > 0
            
            # Verify error is written to report - we can't check exact content
            # but we can verify that write was called multiple times for error handling
            handle = m_open()
            assert handle.write.call_count > 0
    
    def test_generate_report_directory_not_found(self, sample_config):
        """Test handling of directory not found."""
        # Mock file operations
        m_open = mock_open()
        
        # Create a side effect function for Path.exists
        def mock_exists(path):
            # First directory doesn't exist, second one does
            return "/test/dir1" not in str(path)
        
        with patch("builtins.open", m_open), \
             patch("json.load", return_value=sample_config), \
             patch.object(ConfigValidator, "validate"), \
             patch("pathlib.Path.exists", side_effect=mock_exists), \
             patch.object(DependencyAnalyzerFactory, "create_analyzers", return_value=[]):
            
            # Create and run the generator
            generator = DependencyReportGenerator()
            generator.generate_report("test_config.json")
            
            # Verify the factory is only called for the second directory
            # Note: we can't check the exact arguments due to the cache instance
            assert DependencyAnalyzerFactory.create_analyzers.call_count == 1
            args, _ = DependencyAnalyzerFactory.create_analyzers.call_args
            assert args[0] == sample_config["Directories"][1]["Path"]
            assert args[1] == sample_config["Directories"][1]["Environments"]
            
            # Verify error is written to report for first directory
            handle = m_open()
            assert handle.write.call_count > 0
