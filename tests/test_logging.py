"""
Tests for the logging module.

This module contains unit tests for the logging configuration
and helper functions in the logging module.
"""

import pytest
import logging
import os
from unittest.mock import patch, mock_open, MagicMock, call
from pathlib import Path

from ..core.logging import setup_logging, get_logger


class TestLogging:
    """Test cases for the logging module."""
    
    def test_setup_logging_default_params(self):
        """Test setting up logging with default parameters."""
        # Mock logging.basicConfig and logging.getLogger
        with patch('logging.basicConfig') as mock_basic_config, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler, \
             patch('logging.Formatter') as mock_formatter, \
             patch('os.makedirs') as mock_makedirs:
            
            # Create mock objects for handler
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Create mock objects for root logger
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            # Call setup_logging with default parameters
            setup_logging()
            
            # Verify logging.basicConfig was called with the expected parameters
            mock_basic_config.assert_called_once()
            args, kwargs = mock_basic_config.call_args
            assert kwargs['filename'] == "plutonium.log"
            assert kwargs['level'] == logging.INFO
            assert kwargs['filemode'] == "a"  # Append mode by default
            
            # Verify a console handler was created and added to the root logger
            mock_stream_handler.assert_called_once()
            mock_handler.setLevel.assert_called_once_with(logging.INFO)
            mock_handler.setFormatter.assert_called_once()
            mock_root_logger.addHandler.assert_called_once_with(mock_handler)
            
            # Verify log info message
            mock_root_logger.info.assert_called_once_with("Logging initialized")
    
    def test_setup_logging_custom_params(self):
        """Test setting up logging with custom parameters."""
        # Mock logging.basicConfig and logging.getLogger
        with patch('logging.basicConfig') as mock_basic_config, \
             patch('logging.getLogger') as mock_get_logger, \
             patch('logging.StreamHandler') as mock_stream_handler, \
             patch('logging.Formatter') as mock_formatter, \
             patch('os.makedirs') as mock_makedirs:
            
            # Create mock objects for handler
            mock_handler = MagicMock()
            mock_stream_handler.return_value = mock_handler
            
            # Create mock objects for root logger
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger
            
            # Call setup_logging with custom parameters
            custom_log_file = "custom.log"
            custom_log_level = logging.DEBUG
            custom_file_mode = "w"  # Overwrite mode
            
            setup_logging(
                log_file=custom_log_file,
                level=custom_log_level,
                file_mode=custom_file_mode
            )
            
            # Verify logging.basicConfig was called with the expected parameters
            mock_basic_config.assert_called_once()
            args, kwargs = mock_basic_config.call_args
            assert kwargs['filename'] == custom_log_file
            assert kwargs['level'] == custom_log_level
            assert kwargs['filemode'] == custom_file_mode
            
            # Verify a console handler was created and added to the root logger
            mock_stream_handler.assert_called_once()
            mock_handler.setLevel.assert_called_once_with(custom_log_level)
            mock_handler.setFormatter.assert_called_once()
            mock_root_logger.addHandler.assert_called_once_with(mock_handler)
    
    def test_setup_logging_creates_directory(self):
        """Test that setup_logging creates the log directory if it doesn't exist."""
        log_file = "logs/plutonium.log"
        
        # Mock the necessary functions
        with patch('logging.basicConfig'), \
             patch('logging.getLogger'), \
             patch('logging.StreamHandler'), \
             patch('logging.Formatter'), \
             patch('os.makedirs') as mock_makedirs, \
             patch('pathlib.Path.parent', new_callable=MagicMock) as mock_parent:
            
            # Set up the mock parent path
            mock_parent_path = MagicMock()
            mock_parent.return_value = mock_parent_path
            
            # Call setup_logging with a log file in a subdirectory
            setup_logging(log_file=log_file)
            
            # Verify os.makedirs was called to create the directory
            mock_makedirs.assert_called_once()
    
    def test_get_logger(self):
        """Test getting a logger with a specific name."""
        # Mock logging.getLogger
        with patch('logging.getLogger') as mock_get_logger:
            # Call get_logger with a specific name
            logger_name = "test_logger"
            logger = get_logger(logger_name)
            
            # Verify logging.getLogger was called with the expected name
            mock_get_logger.assert_called_once_with(logger_name)
