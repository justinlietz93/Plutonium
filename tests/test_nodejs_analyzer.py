"""
Tests for the NodeJsAnalyzer.

This module contains unit tests for the NodeJsAnalyzer class,
which is responsible for analyzing Node.js dependencies.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from ..analyzers.nodejs_analyzer import NodeJsAnalyzer
from ..core.cache import VersionCache
from ..core.exceptions import ParsingError, NetworkError


class TestNodeJsAnalyzer:
    """Test cases for the NodeJsAnalyzer."""
    
    @pytest.fixture
    def nodejs_analyzer(self):
        """Create a NodeJsAnalyzer instance with a mock cache."""
        mock_cache = MagicMock(spec=VersionCache)
        return NodeJsAnalyzer(cache=mock_cache)
    
    @pytest.fixture
    def sample_package_json(self):
        """Create a sample package.json content."""
        return {
            "name": "test-package",
            "version": "1.0.0",
            "dependencies": {
                "express": "^4.17.1",
                "lodash": "~4.17.15"
            },
            "devDependencies": {
                "jest": "^26.0.1"
            }
        }
    
    def test_environment_name(self, nodejs_analyzer):
        """Test that the environment_name property returns the correct value."""
        assert nodejs_analyzer.environment_name == "Node.js"
    
    def test_get_dependency_file_path(self, nodejs_analyzer):
        """Test getting the dependency file path."""
        with patch('pathlib.Path.exists', return_value=True):
            path = nodejs_analyzer._get_dependency_file_path("test_dir")
            assert path == Path("test_dir") / "package.json"
    
    def test_get_dependency_file_path_not_found(self, nodejs_analyzer):
        """Test getting the dependency file path when it doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                nodejs_analyzer._get_dependency_file_path("test_dir")
    
    def test_parse_dependencies(self, nodejs_analyzer, sample_package_json):
        """Test parsing dependencies from package.json."""
        m_open = mock_open(read_data=json.dumps(sample_package_json))
        
        with patch("builtins.open", m_open):
            dependencies = nodejs_analyzer._parse_dependencies(Path("test_dir/package.json"))
            
            # Check that we have the expected dependencies
            assert len(dependencies) == 3
            assert dependencies["express"] == "4.17.1"  # ^ removed
            assert dependencies["lodash"] == "4.17.15"  # ~ removed
            assert dependencies["jest"] == "26.0.1"     # ^ removed
    
    def test_parse_dependencies_error(self, nodejs_analyzer):
        """Test handling of errors when parsing package.json."""
        with patch("builtins.open", side_effect=IOError("File read error")):
            with pytest.raises(ParsingError):
                nodejs_analyzer._parse_dependencies(Path("test_dir/package.json"))
    
    def test_get_latest_version_from_cache(self, nodejs_analyzer):
        """Test getting the latest version from cache."""
        # Setup mock cache to return a hit
        nodejs_analyzer.cache.get.return_value = "5.0.0"
        
        version = nodejs_analyzer.get_latest_version("express")
        
        # Verify cache was checked with the correct key
        nodejs_analyzer.cache.get.assert_called_once_with("npm:express")
        
        # Verify we got the cached version
        assert version == "5.0.0"
    
    def test_get_latest_version_from_api(self, nodejs_analyzer):
        """Test getting the latest version from the npm API."""
        # Setup mock cache to return a miss, then a mock response for the API
        nodejs_analyzer.cache.get.return_value = None
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "dist-tags": {
                "latest": "5.0.0"
            }
        }
        
        with patch("requests.get", return_value=mock_response):
            version = nodejs_analyzer.get_latest_version("express")
            
            # Verify cache was checked
            nodejs_analyzer.cache.get.assert_called_once()
            
            # Verify the version was cached
            nodejs_analyzer.cache.set.assert_called_once_with("npm:express", "5.0.0")
            
            # Verify we got the expected version
            assert version == "5.0.0"
    
    def test_get_latest_version_network_error(self, nodejs_analyzer):
        """Test handling of network errors when getting the latest version."""
        # Setup cache miss
        nodejs_analyzer.cache.get.return_value = None
        
        with patch("requests.get", side_effect=Exception("Network error")):
            with pytest.raises(NetworkError):
                nodejs_analyzer.get_latest_version("express")
    
    def test_get_installed_dependencies_with_latest(self, nodejs_analyzer):
        """Test getting the latest versions for all dependencies."""
        # Mock get_latest_version to return predictable values
        nodejs_analyzer.get_latest_version = MagicMock(side_effect=lambda pkg: f"{pkg}-latest")
        
        dependencies = {
            "express": "4.17.1",
            "lodash": "4.17.15"
        }
        
        result = nodejs_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we called get_latest_version for each dependency
        assert nodejs_analyzer.get_latest_version.call_count == len(dependencies)
        
        # Check the result format
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == f"{pkg}-latest"
    
    def test_get_installed_dependencies_with_latest_error(self, nodejs_analyzer):
        """Test handling of errors when getting the latest versions."""
        # Mock get_latest_version to raise an exception
        nodejs_analyzer.get_latest_version = MagicMock(side_effect=Exception("API error"))
        
        dependencies = {
            "express": "4.17.1",
            "problematic-package": "1.0.0"
        }
        
        result = nodejs_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we still get a result with error indicators
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == "Error fetching"
    
    def test_analyze_dependencies(self, nodejs_analyzer, sample_package_json):
        """Test analyzing dependencies and writing the report."""
        # Mock _get_dependency_file_path
        with patch.object(
            nodejs_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/package.json")
        ):
            # Mock _parse_dependencies
            with patch.object(
                nodejs_analyzer, "_parse_dependencies", return_value={
                    "express": "4.17.1",
                    "lodash": "4.17.15"
                }
            ):
                # Mock _get_installed_dependencies_with_latest
                with patch.object(
                    nodejs_analyzer, "_get_installed_dependencies_with_latest", return_value=[
                        ("express", "4.17.1", "5.0.0"),
                        ("lodash", "4.17.15", "4.17.20")
                    ]
                ):
                    # Mock write_to_report
                    with patch.object(nodejs_analyzer, "write_to_report") as mock_write:
                        # Run the analyze method
                        nodejs_analyzer.analyze_dependencies("test_dir", "output.md")
                        
                        # Verify write_to_report was called
                        mock_write.assert_called_once()
                        
                        # Get the content that would be written
                        args, _ = mock_write.call_args
                        output_file, content = args
                        
                        # Verify the output file is correct
                        assert output_file == "output.md"
                        
                        # Verify the content includes the dependencies
                        assert "express" in content
                        assert "lodash" in content
                        assert "4.17.1" in content
                        assert "5.0.0" in content
                        assert "4.17.15" in content
                        assert "4.17.20" in content
    
    def test_analyze_dependencies_no_dependencies(self, nodejs_analyzer):
        """Test analyzing when no dependencies are found."""
        # Mock the various methods
        with patch.object(
            nodejs_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/package.json")
        ), patch.object(
            nodejs_analyzer, "_parse_dependencies", return_value={}
        ), patch.object(
            nodejs_analyzer, "write_to_report"
        ) as mock_write:
            
            # Run the analyze method
            nodejs_analyzer.analyze_dependencies("test_dir", "output.md")
            
            # Verify write_to_report was called with "No dependencies found"
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            output_file, content = args
            assert "No dependencies found" in content
    
    def test_analyze_dependencies_error(self, nodejs_analyzer):
        """Test handling of errors during analysis."""
        # Mock _get_dependency_file_path to raise an error
        with patch.object(
            nodejs_analyzer, "_get_dependency_file_path", side_effect=FileNotFoundError("File not found")
        ), patch.object(
            nodejs_analyzer, "write_to_report"
        ) as mock_write:
            
            # Run the analyze method and expect it to re-raise the error
            with pytest.raises(FileNotFoundError):
                nodejs_analyzer.analyze_dependencies("test_dir", "output.md")
            
            # Verify error was written to the report
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            output_file, content = args
            assert "Error" in content
