"""
Report Formatter module.

This module provides functionality for formatting dependency analysis results
as Markdown and writing them to a report file.
"""

import logging
import os
from pathlib import Path
from typing import List, Tuple


class ReportFormatter:
    """Class to format dependency analysis results as Markdown and write to a report file."""
    
    def __init__(self):
        """Initialize the report formatter with a logger."""
        self.logger = logging.getLogger("report_formatter")
    
    def format_markdown_section(self, environment_name: str, directory: str, dependencies: List[Tuple[str, str, str, List[str]]]) -> str:
        """
        Format the dependencies as a Markdown section.
        
        Args:
            environment_name: The name of the environment (e.g., "Node.js", "Python")
            directory: The directory being analyzed
            dependencies: A list of tuples (package_name, current_version, latest_version, vulnerabilities)
            
        Returns:
            A formatted Markdown string
        """
        if not dependencies:
            return f"## {environment_name} Dependencies in {directory}\n\nNo dependencies found.\n\n"
        
        lines = [f"## {environment_name} Dependencies in {directory}\n\n"]
        lines.append("| Package | Current Version | Latest Version | Security Issues |\n")
        lines.append("|---------|----------------|----------------|-----------------|\n")
        
        for package, current, latest, vulnerabilities in sorted(dependencies):
            status = "⬆️" if current != latest else "✅"
            if vulnerabilities and vulnerabilities[0] not in ["None", "Error fetching", "Error processing"]:
                vuln_str = f"🛑 {', '.join(vulnerabilities)}"
            else:
                vuln_str = ", ".join(vulnerabilities) if vulnerabilities else "None"
            lines.append(f"| {package} | {current} | {latest} {status} | {vuln_str} |\n")
        
        lines.append("\n")
        return "".join(lines)
    
    def write_to_report(self, output_file: str, content: str, mode: str = 'a') -> None:
        """
        Write content to the report file.
        
        Args:
            output_file: The path to the output file
            content: The content to write
            mode: The file mode ('a' for append, 'w' for write/overwrite)
        """
        self.logger.debug(f"Attempting to write to report file: {output_file} with mode: {mode}")
        output_path = Path(output_file)
        output_dir = output_path.parent
        self.logger.debug(f"Output directory: {output_dir}")
        if str(output_dir) and output_dir != Path('.'):  # Only create directory if it's not empty
            self.logger.debug(f"Creating directory: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)
        else:
            self.logger.debug("No directory component in output path; skipping makedirs")
        self.logger.debug(f"Checking write permissions for directory: {output_dir}")
        if not os.access(output_dir, os.W_OK):
            raise PermissionError(f"No write permissions for directory: {output_dir}")
        self.logger.debug(f"Writing content to {output_file}")
        with open(output_file, mode, encoding='utf-8') as f:
            f.write(content)
        self.logger.debug(f"Successfully wrote to {output_file}")