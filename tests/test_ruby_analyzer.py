"""
Tests for the RubyAnalyzer.

This module contains unit tests for the RubyAnalyzer class,
which is responsible for analyzing Ruby dependencies.
"""

import pytest
import re
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from ..analyzers.ruby_analyzer import RubyAnalyzer
from ..core.cache import VersionCache
from ..core.exceptions import ParsingError, NetworkError


class TestRubyAnalyzer:
    """Test cases for the RubyAnalyzer."""
    
    @pytest.fixture
    def ruby_analyzer(self):
        """Create a RubyAnalyzer instance with a mock cache."""
        mock_cache = MagicMock(spec=VersionCache)
        return RubyAnalyzer(cache=mock_cache)
    
    @pytest.fixture
    def sample_gemfile(self):
        """Create a sample Gemfile content."""
        return """
# A sample Gemfile
source "https://rubygems.org"

gem "rails", "6.1.4"
gem "pg", "~> 1.2.3"
gem "puma", ">= 5.3.2"
gem "bootsnap", require: false
gem 'devise'

group :development, :test do
  gem "debug"
  gem "rspec-rails"
end

group :development do
  gem "web-console"
end

group :test do
  gem "capybara"
  gem "selenium-webdriver"
end
        """
    
    def test_environment_name(self, ruby_analyzer):
        """Test that the environment_name property returns the correct value."""
        assert ruby_analyzer.environment_name == "Ruby"
    
    def test_get_dependency_file_path(self, ruby_analyzer):
        """Test getting the dependency file path."""
        with patch('pathlib.Path.exists', return_value=True):
            path = ruby_analyzer._get_dependency_file_path("test_dir")
            assert path == Path("test_dir") / "Gemfile"
    
    def test_get_dependency_file_path_not_found(self, ruby_analyzer):
        """Test getting the dependency file path when it doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                ruby_analyzer._get_dependency_file_path("test_dir")
    
    def test_parse_dependencies(self, ruby_analyzer, sample_gemfile):
        """Test parsing dependencies from Gemfile."""
        m_open = mock_open(read_data=sample_gemfile)
        
        with patch("builtins.open", m_open):
            dependencies = ruby_analyzer._parse_dependencies(Path("test_dir/Gemfile"))
            
            # Check that we have the expected dependencies
            assert len(dependencies) >= 10
            assert dependencies["rails"] == "6.1.4"
            assert dependencies["pg"] == "1.2.3"  # ~ removed
            assert dependencies["puma"] == "5.3.2"  # >= removed
            assert dependencies["devise"] == "Not specified"
            assert dependencies["debug"] == "Not specified"
    
    def test_parse_dependencies_error(self, ruby_analyzer):
        """Test handling of errors when parsing Gemfile."""
        with patch("builtins.open", side_effect=IOError("File read error")):
            with pytest.raises(ParsingError):
                ruby_analyzer._parse_dependencies(Path("test_dir/Gemfile"))
    
    def test_get_latest_version_from_cache(self, ruby_analyzer):
        """Test getting the latest version from cache."""
        # Setup mock cache to return a hit
        ruby_analyzer.cache.get.return_value = "7.0.4"
        
        version = ruby_analyzer.get_latest_version("rails")
        
        # Verify cache was checked with the correct key
        ruby_analyzer.cache.get.assert_called_once_with("rubygems:rails")
        
        # Verify we got the cached version
        assert version == "7.0.4"
    
    def test_get_latest_version_from_api(self, ruby_analyzer):
        """Test getting the latest version from the RubyGems API."""
        # Setup mock cache to return a miss, then a mock response for the API
        ruby_analyzer.cache.get.return_value = None
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "version": "7.0.4"
        }
        
        with patch("requests.get", return_value=mock_response):
            version = ruby_analyzer.get_latest_version("rails")
            
            # Verify cache was checked
            ruby_analyzer.cache.get.assert_called_once()
            
            # Verify the version was cached
            ruby_analyzer.cache.set.assert_called_once_with("rubygems:rails", "7.0.4")
            
            # Verify we got the expected version
            assert version == "7.0.4"
    
    def test_get_latest_version_network_error(self, ruby_analyzer):
        """Test handling of network errors when getting the latest version."""
        # Setup cache miss
        ruby_analyzer.cache.get.return_value = None
        
        with patch("requests.get", side_effect=Exception("Network error")):
            with pytest.raises(NetworkError):
                ruby_analyzer.get_latest_version("rails")
    
    def test_get_installed_dependencies_with_latest(self, ruby_analyzer):
        """Test getting the latest versions for all dependencies."""
        # Mock get_latest_version to return predictable values
        ruby_analyzer.get_latest_version = MagicMock(side_effect=lambda pkg: f"{pkg}-latest")
        
        dependencies = {
            "rails": "6.1.4",
            "pg": "1.2.3"
        }
        
        result = ruby_analyzer._get_installed_dependencies_with_latest(dependencies)
        
        # Verify we called get_latest_version for each dependency
        assert ruby_analyzer.get_latest_version.call_count == len(dependencies)
        
        # Check the result format
        assert len(result) == len(dependencies)
        for pkg, current, latest in result:
            assert pkg in dependencies
            assert current == dependencies[pkg]
            assert latest == f"{pkg}-latest"
    
    def test_analyze_dependencies(self, ruby_analyzer, sample_gemfile):
        """Test analyzing dependencies and writing the report."""
        # Mock _get_dependency_file_path
        with patch.object(
            ruby_analyzer, "_get_dependency_file_path", return_value=Path("test_dir/Gemfile")
        ):
            # Mock _parse_dependencies
            with patch.object(
                ruby_analyzer, "_parse_dependencies", return_value={
                    "rails": "6.1.4",
                    "pg": "1.2.3"
                }
            ):
                # Mock _get_installed_dependencies_with_latest
                with patch.object(
                    ruby_analyzer, "_get_installed_dependencies_with_latest", return_value=[
                        ("rails", "6.1.4", "7.0.4"),
                        ("pg", "1.2.3", "1.4.5")
                    ]
                ):
                    # Mock write_to_report
                    with patch.object(ruby_analyzer, "write_to_report") as mock_write:
                        # Run the analyze method
                        ruby_analyzer.analyze_dependencies("test_dir", "output.md")
                        
                        # Verify write_to_report was called
                        mock_write.assert_called_once()
                        
                        # Get the content that would be written
                        args, _ = mock_write.call_args
                        output_file, content = args
                        
                        # Verify the output file is correct
                        assert output_file == "output.md"
                        
                        # Verify the content includes the dependencies
                        assert "rails" in content
                        assert "pg" in content
                        assert "6.1.4" in content
                        assert "7.0.4" in content
                        assert "1.2.3" in content
                        assert "1.4.5" in content
