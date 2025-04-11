"""
Factory module for creating dependency analyzers.

This module provides a factory for creating dependency analyzers
based on the environment and checking for the existence of dependency files.
"""

import logging
from pathlib import Path
from typing import List, Optional

from ..analyzers.interface import IDependencyAnalyzer
from ..core.cache import VersionCache
from ..core.constants import SUPPORTED_ENVIRONMENTS, DEPENDENCY_FILES

# Import all concrete analyzer classes
# These will be implemented in subsequent steps
from ..analyzers.nodejs_analyzer import NodeJsAnalyzer
from ..analyzers.python_analyzer import PythonAnalyzer
from ..analyzers.ruby_analyzer import RubyAnalyzer
from ..analyzers.maven_analyzer import MavenAnalyzer
from ..analyzers.go_analyzer import GoAnalyzer


class DependencyAnalyzerFactory:
    """Factory for creating dependency analyzers."""
    
    @staticmethod
    def create_analyzers(directory: str, environments: List[str], 
                         cache: Optional[VersionCache] = None) -> List[IDependencyAnalyzer]:
        """
        Create analyzers for the specified environments.
        
        Args:
            directory: The directory to analyze
            environments: List of environments to analyze
            cache: Optional VersionCache instance to share across analyzers
            
        Returns:
            A list of dependency analyzers
        """
        analyzers = []
        logger = logging.getLogger("factory")
        
        # Create a shared cache if none is provided
        if cache is None:
            cache = VersionCache()
            
        for env in environments:
            # Verify environment is supported
            if env not in SUPPORTED_ENVIRONMENTS:
                logger.warning(f"Skipping unsupported environment: {env}")
                continue
                
            # Check if dependency file exists
            dependency_file = DEPENDENCY_FILES.get(env)
            dependency_path = Path(directory) / dependency_file
            
            if not dependency_path.exists():
                logger.info(f"Skipping {env} analysis: {dependency_file} not found in {directory}")
                continue
                
            # Create the appropriate analyzer
            analyzer = None
            
            if env == "Node.js":
                analyzer = NodeJsAnalyzer(cache)
            elif env == "Python":
                analyzer = PythonAnalyzer(cache)
            elif env == "Ruby":
                analyzer = RubyAnalyzer(cache)
            elif env == "Maven":
                analyzer = MavenAnalyzer(cache)
            elif env == "Go":
                analyzer = GoAnalyzer(cache)
                
            if analyzer:
                logger.info(f"Created analyzer for {env}")
                analyzers.append(analyzer)
                
        return analyzers
