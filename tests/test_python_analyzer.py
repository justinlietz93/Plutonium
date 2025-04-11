"""
Tests for the PythonAnalyzer.

This module contains unit tests for the PythonAnalyzer class,
which is responsible for analyzing Python dependencies.
"""

import pytest
import re
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from ..analyzers.python_analyzer import PythonAnalyzer
from ..core.cache import VersionCache
from ..core.exceptions import ParsingError, NetworkError


class TestPythonAnalyzer:
    """Test cases for the PythonAnalyzer."""
    
    @pytest.fixture
    def python_analyzer(self):
        """Create a PythonAnalyzer instance with a mock cache."""
        mock_cache = MagicMock(spec=VersionCache)
        return PythonAnalyzer(cache=mock_cache)
    
    @pytest.fixture
    def sample_requirements_txt(self):
        """Create a sample requirements.txt content."""
        return """
# Comment line
requests==2.25.1
Flask>=2.0.0
numpy~=1.20.0
# Another comment
django

# Ignored lines
-e git+https://github.com/example/package.git
--no-binary=:all:
        """
    
    def test_environment_name(self, python_analyzer):
        """Test that the environment_name property returns the correct value."""
        assert python_analyzer.environment_name == "Python"
    
    def test_get_dependency_file_path(self, python_analyzer):
        """Test getting the dependency file path."""
        with patch('pathlib.Path.exists', return_value=True):
            path = python_analyzer._get_dependency_file_path("test_dir")
            assert path == Path("test_dir") / "requirements.txt"
    
    def test_get_dependency_file_path_not_found(self, python_analyzer):
        """Test getting the dependency file path when it doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                python_analyzer._get_dependency_file_path("test_dir")
    
    def test_parse_dependencies(self, python_analyzer, sample_requirements_txt):
        """Test parsing dependencies from requirements.txt."""
        m_open = mock_open(read_data=sample_requirements_txt)
        
        with patch("builtins.open", m_open):
            dependencies = python_analyzer._parse_dependencies(Path("test_dir/requirements.txt"))
            
            # Check that we have the expected dependencies
            assert len(dependencies) == 4
            assert dependencies["requests"] == "2.25.1"
            assert dependencies["flask"] == "2.0.0"  # Normalized, > removed
            assert dependencies["numpy"] == "1.20.0"  # ~ removed
            assert dependencies["django"] == "Not specified"
            
            # Check that we ignored the comment lines and special lines
            assert "-e" not in dependencies
            assert "--no-binary" not in dependencies
    
    def test_parse_dependencies_error(self, python_analyzer):
        """Test handling of errors when parsing requirements.txt."""
        with patch("builtins.open", side_effect=IOError("File read error")):
            with pytest.raises(ParsingError):
                python_analyzer._parse_dependencies(Path("test_dir/requirements.txt"))
    
    def test_get_latest_version_from_cache(self, python_analyzer):
        """Test getting the latest version from cache."""
        # Setup mock cache to return a hit
        python_analyzer.cache.get.return_value = "2.26.0"
        
        version = python_analyzer.get_latest_version("requests")
        
        # Verify cache was checked with the correct key
        python_analyzer.cache.get.assert_called_once_with("pypi:requests")
        
        # Verify we got the cached version
        assert version == "2.26.0"
    
    def test_get_latest_version_from_api(self, python_analyzer):
        """Test getting the latest version from the PyPI API."""
        # Setup mock cache to return a miss, then a mock response for the API
        python_analyzer.cache.get.return_value = None
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "info": {
                "version": "2.26.0"
            }
        }
        
        with patch("requests.get", return_value=mock_response):
            version = python_analyzer.get_latest_version("requests")
            
            # Verify cache was checked
            python_analyzer.cache.get.assert_called_once()
            
            # Verify the version was cached
            python_analyzer.cache.set.assert_called_once_with("pypi:requests", "2.26.0")
            
            # Verify we got the expected version
            assert version == "2.26.0"
    
    def test_get_latest_version_network_error(self, python_analyzer):
        """Test handling of network errors when getting the latest version."""
        # Setup cache miss
        python_analyzer.cache.get.return_value = None
        
        with patch("requests.get", side_effect=Exception("Network error")):
            with pytest.raises(NetworkError):
                python_analyzer.get_latest_version("requests")
    
    def test_get_installed_dependencies_with_latest(self, python_analyzer):
        """Test getting the latest versions for all dependencies."""
        # Mock get_latest_version to return predictable values
        python_analyzer.get_latest_version = MagicMock(side_effect=lambda pkg: f"{pkg}-latest")
        
        dependencies = {
            "requests": "2.25.1",
            "flask": "2.0.0"
        }
        
        result = python_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we called get_latest_version for each dependency
        assert python_analyzer.get_latest_version.call_count == len(dependencies)
        
        # Check the result format
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == f"{pkg}-latest"
    
    def test_get_installed_dependencies_with_latest_error(self, python_analyzer):
        """Test handling of errors when getting the latest versions."""
        # Mock get_latest_version to raise an exception
        python_analyzer.get_latest_version = MagicMock(side_effect=Exception("API error"))
        
        dependencies = {
            "requests": "2.25.1",
            "problematic-package": "1.0.0"
        }
        
        result = python_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we still get a result with error indicators
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == "Error fetching"
    
    def test_analyze_dependencies(self, python_analyzer, sample_requirements_txt):
        """Test analyzing dependencies and writing the report."""
        # Mock _get_dependency_file_path
        with patch.object(
            python_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/requirements.txt")
        ):
            # Mock _parse_dependencies
            with patch.object(
                python_analyzer, "_parse_dependencies", return_value={
                    "requests": "2.25.1",
                    "flask": "2.0.0"
                }
            ):
                # Mock _get_installed_dependencies_with_latest
                with patch.object(
                    python_analyzer, "_get_installed_dependencies_with_latest", return_value=[
                        ("requests", "2.25.1", "2.26.0"),
                        ("flask", "2.0.0", "2.1.0")
                    ]
                ):
                    # Mock write_to_report
                    with patch.object(python_analyzer, "write_to_report") as mock_write:
                        # Run the analyze method
                        python_analyzer.analyze_dependencies("test_dir", "output.md")
                        
                        # Verify write_to_report was called
                        mock_write.assert_called_once()
                        
                        # Get the content that would be written
                        args, _ = mock_write.call_args
                        output_file, content = args
                        
                        # Verify the output file is correct
                        assert output_file == "output.md"
                        
                        # Verify the content includes the dependencies
                        assert "requests" in content
                        assert "flask" in content
                        assert "2.25.1" in content
                        assert "2.26.0" in content
                        assert "2.0.0" in content
                        assert "2.1.0" in content
    
    def test_analyze_dependencies_no_dependencies(self, python_analyzer):
        """Test analyzing when no dependencies are found."""
        # Mock the various methods
        with patch.object(
            python_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/requirements.txt")
        ), patch.object(
            python_analyzer, "_parse_dependencies", return_value={}
        ), patch.object(
            python_analyzer, "write_to_report"
        ) as mock_write:
            
            # Run the analyze method
            python_analyzer.analyze_dependencies("test_dir", "output.md")
            
            # Verify write_to_report was called with "No dependencies found"
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            output_file, content = args
            assert "No dependencies found" in content
    
    def test_analyze_dependencies_error(self, python_analyzer):
        """Test handling of errors during analysis."""
        # Mock _get_dependency_file_path to raise an error
        with patch.object(
            python_analyzer, "_get_dependency_file_path", side_effect=FileNotFoundError("File not found")
        ), patch.object(
            python_analyzer, "write_to_report"
        ) as mock_write:
            
            # Run the analyze method and expect it to re-raise the error
            with pytest.raises(FileNotFoundError):
                python_analyzer.analyze_dependencies("test_dir", "output.md")
            
            # Verify error was written to the report
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            output_file, content = args
            assert "Error" in content
