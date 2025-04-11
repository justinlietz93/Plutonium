"""
Tests for the DependencyAnalyzerFactory.

This module contains unit tests for the DependencyAnalyzerFactory class,
which is responsible for creating analyzer instances based on environment
and dependency file presence.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from ..core.factory import DependencyAnalyzerFactory
from ..analyzers.nodejs_analyzer import NodeJsAnalyzer
from ..analyzers.python_analyzer import PythonAnalyzer
from ..analyzers.ruby_analyzer import RubyAnalyzer
from ..analyzers.maven_analyzer import MavenAnalyzer
from ..analyzers.go_analyzer import GoAnalyzer


class TestDependencyAnalyzerFactory:
    """Test cases for the DependencyAnalyzerFactory."""
    
    def test_create_nodejs_analyzer(self):
        """Test creating a Node.js analyzer when package.json exists."""
        with patch('pathlib.Path.exists', return_value=True):
            analyzers = DependencyAnalyzerFactory.create_analyzers("test_dir", ["Node.js"])
            assert len(analyzers) == 1
            assert isinstance(analyzers[0], NodeJsAnalyzer)
    
    def test_create_python_analyzer(self):
        """Test creating a Python analyzer when requirements.txt exists."""
        with patch('pathlib.Path.exists', return_value=True):
            analyzers = DependencyAnalyzerFactory.create_analyzers("test_dir", ["Python"])
            assert len(analyzers) == 1
            assert isinstance(analyzers[0], PythonAnalyzer)
    
    def test_create_ruby_analyzer(self):
        """Test creating a Ruby analyzer when Gemfile exists."""
        with patch('pathlib.Path.exists', return_value=True):
            analyzers = DependencyAnalyzerFactory.create_analyzers("test_dir", ["Ruby"])
            assert len(analyzers) == 1
            assert isinstance(analyzers[0], RubyAnalyzer)
    
    def test_create_maven_analyzer(self):
        """Test creating a Maven analyzer when pom.xml exists."""
        with patch('pathlib.Path.exists', return_value=True):
            analyzers = DependencyAnalyzerFactory.create_analyzers("test_dir", ["Maven"])
            assert len(analyzers) == 1
            assert isinstance(analyzers[0], MavenAnalyzer)
    
    def test_create_go_analyzer(self):
        """Test creating a Go analyzer when go.mod exists."""
        with patch('pathlib.Path.exists', return_value=True):
            analyzers = DependencyAnalyzerFactory.create_analyzers("test_dir", ["Go"])
            assert len(analyzers) == 1
            assert isinstance(analyzers[0], GoAnalyzer)
    
    def test_no_file_found(self):
        """Test that no analyzers are created when dependency files don't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            analyzers = DependencyAnalyzerFactory.create_analyzers("test_dir", ["Node.js", "Python"])
            assert len(analyzers) == 0
    
    def test_unsupported_environment(self):
        """Test that unsupported environments are skipped."""
        with patch('pathlib.Path.exists', return_value=True):
            analyzers = DependencyAnalyzerFactory.create_analyzers("test_dir", ["UnsupportedEnv"])
            assert len(analyzers) == 0
    
    def test_multiple_analyzers(self):
        """Test creating multiple analyzers when multiple dependency files exist."""
        # Create a mock side effect function that returns True only for specific paths
        def mock_exists(path):
            # Convert Path to string for comparison
            path_str = str(path)
            return "package.json" in path_str or "requirements.txt" in path_str
        
        with patch('pathlib.Path.exists', side_effect=mock_exists):
            analyzers = DependencyAnalyzerFactory.create_analyzers(
                "test_dir", ["Node.js", "Python", "Ruby", "Maven", "Go"]
            )
            assert len(analyzers) == 2
            # Check that we have the right types of analyzers
            analyzer_types = [type(a) for a in analyzers]
            assert NodeJsAnalyzer in analyzer_types
            assert PythonAnalyzer in analyzer_types
            assert RubyAnalyzer not in analyzer_types
            assert MavenAnalyzer not in analyzer_types
            assert GoAnalyzer not in analyzer_types
    
    def test_shared_cache(self):
        """Test that all analyzers share the same cache instance when provided."""
        with patch('pathlib.Path.exists', return_value=True):
            # Create a mock cache
            mock_cache = MagicMock()
            
            analyzers = DependencyAnalyzerFactory.create_analyzers(
                "test_dir", ["Node.js", "Python"], cache=mock_cache
            )
            
            assert len(analyzers) == 2
            # Verify all analyzers use the same cache instance
            for analyzer in analyzers:
                assert analyzer.cache is mock_cache
