"""
Logging module for the dependency analyzer.

This module provides a configurable logging setup for the dependency analyzer application.
"""

import logging
import os
from pathlib import Path


def setup_logging(log_file="plutonium.log", level=logging.INFO, file_mode="a"):
    """
    Set up logging configuration for the application.
    
    Args:
        log_file: Path to the log file
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        file_mode: File mode for the log file ('a' to append, 'w' to overwrite)
    """
    # Ensure the log directory exists
    log_path = Path(log_file)
    if log_path.parent != Path('.'):
        os.makedirs(log_path.parent, exist_ok=True)
    
    # Configure the root logger
    logging.basicConfig(
        filename=log_file,
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode=file_mode
    )
    
    # Add a console handler to show logs in the console as well
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    
    # Add the console handler to the root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    
    # Log that logging has been set up
    logging.info("Logging initialized")


def get_logger(name):
    """
    Get a logger with the specified name.
    
    Args:
        name: The name for the logger
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)
