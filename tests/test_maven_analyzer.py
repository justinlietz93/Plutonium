"""
Tests for the MavenAnalyzer.

This module contains unit tests for the MavenAnalyzer class,
which is responsible for analyzing Maven dependencies.
"""

import pytest
import requests
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path

from ..analyzers.maven_analyzer import MavenAnalyzer
from ..core.cache import VersionCache
from ..core.exceptions import ParsingError, NetworkError


class TestMavenAnalyzer:
    """Test cases for the MavenAnalyzer."""
    
    @pytest.fixture
    def maven_analyzer(self):
        """Create a MavenAnalyzer instance with a mock cache."""
        mock_cache = MagicMock(spec=VersionCache)
        return MavenAnalyzer(cache=mock_cache)
    
    @pytest.fixture
    def sample_pom_xml(self):
        """Create a sample pom.xml content."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>demo-app</artifactId>
    <version>1.0-SNAPSHOT</version>

    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <spring.version>5.3.9</spring.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>${spring.version}</version>
        </dependency>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-context</artifactId>
            <version>${spring.version}</version>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <version>1.18.20</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
        """
    
    def test_environment_name(self, maven_analyzer):
        """Test that the environment_name property returns the correct value."""
        assert maven_analyzer.environment_name == "Maven"
    
    def test_get_dependency_file_path(self, maven_analyzer):
        """Test getting the dependency file path."""
        with patch('pathlib.Path.exists', return_value=True):
            path = maven_analyzer._get_dependency_file_path("test_dir")
            assert path == Path("test_dir") / "pom.xml"
    
    def test_get_dependency_file_path_not_found(self, maven_analyzer):
        """Test getting the dependency file path when it doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                maven_analyzer._get_dependency_file_path("test_dir")
    
    def test_parse_dependencies(self, maven_analyzer, sample_pom_xml):
        """Test parsing dependencies from pom.xml."""
        # Mock open to return our sample pom.xml
        m_open = mock_open(read_data=sample_pom_xml)
        
        # Mock ET.parse to return a proper ElementTree
        with patch("builtins.open", m_open), \
             patch("xml.etree.ElementTree.parse", return_value=ET.ElementTree(ET.fromstring(sample_pom_xml))):
            
            dependencies = maven_analyzer._parse_dependencies(Path("test_dir/pom.xml"))
            
            # Check that we have the expected dependencies
            assert len(dependencies) >= 3  # Excluding test dependencies
            assert "org.springframework:spring-core" in dependencies
            assert dependencies["org.springframework:spring-core"] == "${spring.version}"
            assert dependencies["org.projectlombok:lombok"] == "1.18.20"
    
    def test_parse_dependencies_error(self, maven_analyzer):
        """Test handling of errors when parsing pom.xml."""
        with patch("builtins.open", side_effect=IOError("File read error")):
            with pytest.raises(ParsingError):
                maven_analyzer._parse_dependencies(Path("test_dir/pom.xml"))
    
    def test_get_latest_version_from_cache(self, maven_analyzer):
        """Test getting the latest version from cache."""
        # Setup mock cache to return a hit
        maven_analyzer.cache.get.return_value = "5.3.20"
        
        version = maven_analyzer.get_latest_version("org.springframework:spring-core")
        
        # Verify cache was checked with the correct key
        maven_analyzer.cache.get.assert_called_once_with("maven:org.springframework:spring-core")
        
        # Verify we got the cached version
        assert version == "5.3.20"
    
    def test_get_latest_version_from_api(self, maven_analyzer):
        """Test getting the latest version from the Maven Central API."""
        # Setup mock cache to return a miss, then a mock response for the API
        maven_analyzer.cache.get.return_value = None
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {
                "docs": [
                    {
                        "g": "org.springframework",
                        "a": "spring-core",
                        "latestVersion": "5.3.20",
                        "timestamp": 1650000000000,
                        "v": "5.3.20"
                    },
                    {
                        "g": "org.springframework",
                        "a": "spring-core",
                        "v": "5.3.19",
                        "timestamp": 1645000000000
                    }
                ]
            }
        }
        
        with patch("requests.get", return_value=mock_response):
            version = maven_analyzer.get_latest_version("org.springframework:spring-core")
            
            # Verify cache was checked
            maven_analyzer.cache.get.assert_called_once()
            
            # Verify the version was cached
            maven_analyzer.cache.set.assert_called_once_with(
                "maven:org.springframework:spring-core", "5.3.20"
            )
            
            # Verify we got the expected version
            assert version == "5.3.20"
    
    def test_get_latest_version_api_error(self, maven_analyzer):
        """Test handling of API errors when getting the latest version."""
        # Setup cache miss
        maven_analyzer.cache.get.return_value = None
        
        # Mock API call to raise an exception
        with patch("requests.get", side_effect=requests.RequestException("API error")):
            with pytest.raises(NetworkError):
                maven_analyzer.get_latest_version("org.springframework:spring-core")
    
    def test_get_installed_dependencies_with_latest(self, maven_analyzer):
        """Test getting the latest versions for all dependencies."""
        # Mock get_latest_version to return a predictable pattern
        maven_analyzer.get_latest_version = MagicMock(side_effect=lambda pkg: f"{pkg}-latest")
        
        dependencies = {
            "org.springframework:spring-core": "5.3.9",
            "org.projectlombok:lombok": "1.18.20"
        }
        
        result = maven_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we called get_latest_version for each dependency
        assert maven_analyzer.get_latest_version.call_count == len(dependencies)
        
        # Check the result format
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == f"{pkg}-latest"
    
    def test_analyze_dependencies(self, maven_analyzer, sample_pom_xml):
        """Test analyzing dependencies and writing the report."""
        # Mock _get_dependency_file_path
        with patch.object(
            maven_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/pom.xml")
        ):
            # Mock _parse_dependencies
            with patch.object(
                maven_analyzer, "_parse_dependencies", return_value={
                    "org.springframework:spring-core": "5.3.9",
                    "org.projectlombok:lombok": "1.18.20"
                }
            ):
                # Mock _get_installed_dependencies_with_latest
                with patch.object(
                    maven_analyzer, "_get_installed_dependencies_with_latest", return_value=[
                        ("org.springframework:spring-core", "5.3.9", "5.3.20"),
                        ("org.projectlombok:lombok", "1.18.20", "1.18.22")
                    ]
                ):
                    # Mock write_to_report
                    with patch.object(maven_analyzer, "write_to_report") as mock_write:
                        # Run the analyze method
                        maven_analyzer.analyze_dependencies("test_dir", "output.md")
                        
                        # Verify write_to_report was called
                        mock_write.assert_called_once()
                        
                        # Get the content that would be written
                        args, _ = mock_write.call_args
                        output_file, content = args
                        
                        # Verify the output file is correct
                        assert output_file == "output.md"
                        
                        # Verify the content includes the dependencies
                        assert "spring-core" in content
                        assert "lombok" in content
                        assert "5.3.9" in content
                        assert "5.3.20" in content
                        assert "1.18.20" in content
                        assert "1.18.22" in content
    
    def test_analyze_dependencies_no_dependencies(self, maven_analyzer):
        """Test analyzing when no dependencies are found."""
        # Mock _get_dependency_file_path
        with patch.object(
            maven_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/pom.xml")
        ):
            # Mock _parse_dependencies to return empty dict
            with patch.object(maven_analyzer, "_parse_dependencies", return_value={}):
                # Mock write_to_report
                with patch.object(maven_analyzer, "write_to_report") as mock_write:
                    # Run the analyze method
                    maven_analyzer.analyze_dependencies("test_dir", "output.md")
                    
                    # Verify write_to_report was called with "No dependencies found"
                    mock_write.assert_called_once()
                    args, _ = mock_write.call_args
                    output_file, content = args
                    assert "No dependencies" in content
    
    def test_analyze_dependencies_error(self, maven_analyzer):
        """Test handling of errors during analysis."""
        # Mock _get_dependency_file_path to raise an exception
        error_message = "File not found"
        with patch.object(
            maven_analyzer, "_get_dependency_file_path", 
            side_effect=FileNotFoundError(error_message)
        ), patch.object(maven_analyzer, "write_to_report") as mock_write:
            
            # This should catch the exception and write error to report
            with pytest.raises(FileNotFoundError):
                maven_analyzer.analyze_dependencies("test_dir", "output.md")
            
            # Verify error was written to report
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            output_file, content = args
            assert "Error" in content
            assert error_message in content
