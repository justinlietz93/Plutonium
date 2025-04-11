"""
Tests for the GoAnalyzer.

This module contains unit tests for the GoAnalyzer class,
which is responsible for analyzing Go dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from ..analyzers.go_analyzer import GoAnalyzer
from ..core.cache import VersionCache
from ..core.exceptions import ParsingError, NetworkError


class TestGoAnalyzer:
    """Test cases for the GoAnalyzer."""
    
    @pytest.fixture
    def go_analyzer(self):
        """Create a GoAnalyzer instance with a mock cache."""
        mock_cache = MagicMock(spec=VersionCache)
        return GoAnalyzer(cache=mock_cache)
    
    @pytest.fixture
    def sample_go_mod(self):
        """Create a sample go.mod content."""
        return """module example.com/myproject

go 1.16

require (
	github.com/gin-gonic/gin v1.7.2
	github.com/go-playground/validator/v10 v10.6.1 // indirect
	github.com/golang/protobuf v1.5.2 // indirect
	github.com/json-iterator/go v1.1.11 // indirect
	github.com/stretchr/testify v1.7.0
)

require github.com/sirupsen/logrus v1.8.1

exclude github.com/ugorji/go v1.1.4
replace github.com/go-playground/validator => github.com/go-playground/validator/v10 v10.0.0
        """
    
    def test_environment_name(self, go_analyzer):
        """Test that the environment_name property returns the correct value."""
        assert go_analyzer.environment_name == "Go"
    
    def test_get_dependency_file_path(self, go_analyzer):
        """Test getting the dependency file path."""
        with patch('pathlib.Path.exists', return_value=True):
            path = go_analyzer._get_dependency_file_path("test_dir")
            assert path == Path("test_dir") / "go.mod"
    
    def test_get_dependency_file_path_not_found(self, go_analyzer):
        """Test getting the dependency file path when it doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                go_analyzer._get_dependency_file_path("test_dir")
    
    def test_parse_dependencies(self, go_analyzer, sample_go_mod):
        """Test parsing dependencies from go.mod."""
        m_open = mock_open(read_data=sample_go_mod)
        
        with patch("builtins.open", m_open):
            dependencies = go_analyzer._parse_dependencies(Path("test_dir/go.mod"))
            
            # Check that we have the expected dependencies
            assert len(dependencies) >= 6
            assert dependencies["github.com/gin-gonic/gin"] == "v1.7.2"
            assert dependencies["github.com/stretchr/testify"] == "v1.7.0"
            assert dependencies["github.com/sirupsen/logrus"] == "v1.8.1"
            
            # These are commented as indirect dependencies but we should still pick them up
            assert "github.com/go-playground/validator/v10" in dependencies
            assert "github.com/golang/protobuf" in dependencies
            assert "github.com/json-iterator/go" in dependencies
    
    def test_parse_dependencies_error(self, go_analyzer):
        """Test handling of errors when parsing go.mod."""
        with patch("builtins.open", side_effect=IOError("File read error")):
            with pytest.raises(ParsingError):
                go_analyzer._parse_dependencies(Path("test_dir/go.mod"))
    
    def test_get_latest_version_from_cache(self, go_analyzer):
        """Test getting the latest version from cache."""
        # Setup mock cache to return a hit
        go_analyzer.cache.get.return_value = "v1.8.0"
        
        version = go_analyzer.get_latest_version("github.com/gin-gonic/gin")
        
        # Verify cache was checked with the correct key
        go_analyzer.cache.get.assert_called_once_with("go:github.com/gin-gonic/gin")
        
        # Verify we got the cached version
        assert version == "v1.8.0"
    
    def test_get_latest_version_from_api(self, go_analyzer):
        """Test getting the latest version from the Go proxy API."""
        # Setup mock cache to return a miss, then a mock response for the API
        go_analyzer.cache.get.return_value = None
        
        mock_response = MagicMock()
        mock_response.text = """v1.6.0
                                v1.6.1
                                v1.6.2
                                v1.6.3
                                v1.7.0
                                v1.7.1
                                v1.7.2
                                v1.7.3
                                v1.7.4
                                v1.8.0
                                v1.8.1
                                """
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.get", return_value=mock_response):
            version = go_analyzer.get_latest_version("github.com/gin-gonic/gin")
            
            # Verify cache was checked
            go_analyzer.cache.get.assert_called_once()
            
            # Verify the version was cached
            go_analyzer.cache.set.assert_called_once_with("go:github.com/gin-gonic/gin", "v1.8.1")
            
            # Verify we got the expected version (latest should be v1.8.1)
            assert version == "v1.8.1"
    
    def test_get_latest_version_network_error(self, go_analyzer):
        """Test handling of network errors when getting the latest version."""
        # Setup cache miss
        go_analyzer.cache.get.return_value = None
        
        with patch("requests.get", side_effect=Exception("Network error")):
            with pytest.raises(NetworkError):
                go_analyzer.get_latest_version("github.com/gin-gonic/gin")
    
    def test_get_installed_dependencies_with_latest(self, go_analyzer):
        """Test getting the latest versions for all dependencies."""
        # Mock get_latest_version to return predictable values
        go_analyzer.get_latest_version = MagicMock(side_effect=lambda pkg: f"{pkg}-latest")
        
        dependencies = {
            "github.com/gin-gonic/gin": "v1.7.2",
            "github.com/stretchr/testify": "v1.7.0"
        }
        
        result = go_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we called get_latest_version for each dependency
        assert go_analyzer.get_latest_version.call_count == len(dependencies)
        
        # Check the result format
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == f"{pkg}-latest"
    
    def test_get_installed_dependencies_with_latest_error(self, go_analyzer):
        """Test handling of errors when getting the latest versions."""
        # Mock get_latest_version to raise an exception
        go_analyzer.get_latest_version = MagicMock(side_effect=Exception("API error"))
        
        dependencies = {
            "github.com/gin-gonic/gin": "v1.7.2",
            "github.com/problematic-package/pkg": "v1.0.0"
        }
        
        result = go_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we still get a result with error indicators
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == "Error fetching"
    
    def test_analyze_dependencies(self, go_analyzer, sample_go_mod):
        """Test analyzing dependencies and writing the report."""
        # Mock _get_dependency_file_path
        with patch.object(
            go_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/go.mod")
        ):
            # Mock _parse_dependencies
            with patch.object(
                go_analyzer, "_parse_dependencies", return_value={
                    "github.com/gin-gonic/gin": "v1.7.2",
                    "github.com/stretchr/testify": "v1.7.0"
                }
            ):
                # Mock _get_installed_dependencies_with_latest
                with patch.object(
                    go_analyzer, "_get_installed_dependencies_with_latest", return_value=[
                        ("github.com/gin-gonic/gin", "v1.7.2", "v1.8.1"),
                        ("github.com/stretchr/testify", "v1.7.0", "v1.7.0")
                    ]
                ):
                    # Mock write_to_report
                    with patch.object(go_analyzer, "write_to_report") as mock_write:
                        # Run the analyze method
                        go_analyzer.analyze_dependencies("test_dir", "output.md")
                        
                        # Verify write_to_report was called
                        mock_write.assert_called_once()
                        
                        # Get the content that would be written
                        args, _ = mock_write.call_args
                        output_file, content = args
                        
                        # Verify the output file is correct
                        assert output_file == "output.md"
                        
                        # Verify the content includes the dependencies
                        assert "github.com/gin-gonic/gin" in content
                        assert "github.com/stretchr/testify" in content
                        assert "v1.7.2" in content
                        assert "v1.8.1" in content
                        assert "v1.7.0" in content
    
    def test_analyze_dependencies_no_dependencies(self, go_analyzer):
        """Test analyzing when no dependencies are found."""
        # Mock the various methods
        with patch.object(
            go_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/go.mod")
        ), patch.object(
            go_analyzer, "_parse_dependencies", return_value={}
        ), patch.object(
            go_analyzer, "write_to_report"
        ) as mock_write:
            
            # Run the analyze method
            go_analyzer.analyze_dependencies("test_dir", "output.md")
            
            # Verify write_to_report was called with "No dependencies found"
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            output_file, content = args
            assert "No dependencies found" in content
    
    def test_analyze_dependencies_error(self, go_analyzer):
        """Test handling of errors during analysis."""
        # Mock _get_dependency_file_path to raise an error
        with patch.object(
            go_analyzer, "_get_dependency_file_path", side_effect=FileNotFoundError("File not found")
        ), patch.object(
            go_analyzer, "write_to_report"
        ) as mock_write:
            
            # Run the analyze method and expect it to re-raise the error
            with pytest.raises(FileNotFoundError):
                go_analyzer.analyze_dependencies("test_dir", "output.md")
            
            # Verify error was written to report
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            output_file, content = args
            assert "Error" in content
            assert "File not found" in content
