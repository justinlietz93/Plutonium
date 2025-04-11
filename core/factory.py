"""
Factory module for creating dependency analyzers.

This module provides a factory for creating dependency analyzers
based on the environment and checking for the existence of dependency files.
"""

import logging
from pathlib import Path
from typing import List, Optional

# Use relative imports within the package
from ..analyzers.interface import IDependencyAnalyzer
from .cache import VersionCache  # Corrected relative import
from .constants import SUPPORTED_ENVIRONMENTS, DEPENDENCY_FILES # Also correct this one for consistency

# Import all concrete analyzer classes
from ..analyzers.nodejs_analyzer import NodeJsAnalyzer
from ..analyzers.python_analyzer import PythonAnalyzer
from ..analyzers.ruby_analyzer import RubyAnalyzer
from ..analyzers.maven_analyzer import MavenAnalyzer
from ..analyzers.go_analyzer import GoAnalyzer


class DependencyAnalyzerFactory:
    """Factory for creating dependency analyzers."""
    
    @staticmethod
    def create_analyzers(directory: str, environments: List[str], 
                         cache: Optional[VersionCache] = None, nvd_api_key: str = None) -> List[IDependencyAnalyzer]:
        """
        Create analyzers for the specified environments.
        
        Args:
            directory: The directory to analyze
            environments: List of environments to analyze
            cache: Optional VersionCache instance to share across analyzers
            nvd_api_key: Optional NVD API key (not used with VulnCheck NVD++)
            
        Returns:
            A list of dependency analyzers
        """
        analyzers = []
        logger = logging.getLogger("factory")
        logger.debug(f"Creating analyzers with NVD API key: {nvd_api_key} (not used with VulnCheck NVD++)")
        
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
                analyzer = NodeJsAnalyzer(cache=cache, nvd_api_key=nvd_api_key)
            elif env == "Python":
                analyzer = PythonAnalyzer(cache=cache, nvd_api_key=nvd_api_key)
            elif env == "Ruby":
                analyzer = RubyAnalyzer(cache=cache, nvd_api_key=nvd_api_key)
            elif env == "Maven":
                analyzer = MavenAnalyzer(cache=cache, nvd_api_key=nvd_api_key)
            elif env == "Go":
                analyzer = GoAnalyzer(cache=cache, nvd_api_key=nvd_api_key)
                
            if analyzer:
                logger.info(f"Created analyzer for {env}")
                analyzers.append(analyzer)
                
        return analyzers
