# In core/report_formatter.py

import logging
import os
from pathlib import Path
from typing import List, Tuple, Any


class ReportFormatter:
    """Class to format dependency analysis results as Markdown and write to a report file."""

    def __init__(self):
        """Initialize the report formatter with a logger."""
        self.logger = logging.getLogger("report_formatter")

    def format_markdown_section(self, environment_name: str, directory: str, dependencies: List[Tuple[str, str, str, List[str]]]) -> str:
        """
        Format the dependencies as a Markdown section using the specified legend.
        Legend: ✅=Up-to-date, ⚠️=Update available, 🛑=Vulns/Error, ⚙️=Variable, Error/N/A=Skipped/Error Text
        """
        if not isinstance(dependencies, list):
             self.logger.warning(f"Invalid dependencies data received for {environment_name} in {directory}: {type(dependencies)}. Skipping section.")
             return f"## {environment_name} Dependencies in {directory}\n\nError processing dependencies for this section.\n\n"

        if not dependencies:
            return f"## {environment_name} Dependencies in {directory}\n\nNo dependencies processed or found.\n\n"

        lines = [f"## {environment_name} Dependencies in {directory}\n\n"]
        # Headers match the columns being generated
        lines.append("| Package | Current Version | Latest Version | Status | Issues |\n")
        lines.append("|---------|-----------------|----------------|--------|--------|\n")

        for package, current, latest, vulnerabilities in sorted(dependencies):
            # Determine version status symbol based on user legend
            status = "" # Default
            is_latest_valid = latest not in ["Error", "N/A (Not Found)", "N/A (Parse Error)", "N/A (Error)", "N/A (Variable)"]
            # Determine if current version is variable/unknown
            is_current_variable = isinstance(current, str) and (current.startswith(("${","(")) or current == "unknown" or current == "(Complex Specifier)")
            is_variable_overall = is_current_variable or latest == "N/A (Variable)"

            if is_variable_overall:
                status = "⚙️" # Gear for variable
            elif is_latest_valid:
                # Use YELLOW SIGN (⚠️) for update available
                status = "✅" if current == latest else "⚠️"
            # else: status remains "" if latest version lookup failed

            # Format vulnerability/status string based on user legend
            issues_str = "" # Default
            use_red_sign = False

            if isinstance(vulnerabilities, list):
                if not vulnerabilities:
                    # Empty list means successful check, no vulns found
                    issues_str = "None"
                else:
                    first_item = vulnerabilities[0]
                    is_error = first_item.startswith("Error") # e.g., "Error (Timeout)"
                    is_skipped_or_na = first_item.startswith("N/A") # e.g., "N/A (Skipped)"
                    is_real_vuln = not is_error and not is_skipped_or_na

                    if is_real_vuln:
                        # Use RED SIGN (🛑) ONLY for actual vulns found
                        use_red_sign = True
                        issues_str = ", ".join(vulnerabilities)
                    elif is_error:
                        # Use RED SIGN (🛑) also for errors per legend "Vuln found (or Error checking)"
                        use_red_sign = True
                        issues_str = ", ".join(vulnerabilities) # Display the error message itself
                    else: # N/A cases (Skipped, Invalid Version etc.)
                         # Display N/A message directly per "Error / N/A = Error or Skipped Check" legend
                         issues_str = ", ".join(vulnerabilities)
            else:
                 # Treat unexpected data format as an error
                 issues_str = "Error (Vuln Data Format)"
                 use_red_sign = True # Use RED SIGN (🛑) for this error too

            # Prepend red sign if needed
            display_issues_str = f"🛑 {issues_str}" if use_red_sign else issues_str

            # Append the formatted row
            lines.append(f"| {package} | {current} | {latest} | {status} | {display_issues_str} |\n")

        lines.append("\n")
        return "".join(lines)

    # write_to_report method remains the same...
    def write_to_report(self, output_file: str, content: str, mode: str = 'a') -> None:
        # ... (implementation remains the same) ...
        self.logger.debug(f"Attempting to write to report file: {output_file} with mode: {mode}")
        output_path = Path(output_file)
        output_dir = output_path.parent
        try:
            if output_dir and str(output_dir) != '.':
                self.logger.debug(f"Creating directory: {output_dir}")
                output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Checking write permissions for directory: {output_dir}")
            if not os.access(output_dir if output_dir and str(output_dir) != '.' else '.', os.W_OK):
                 raise PermissionError(f"No write permissions for directory: {output_dir}")
            self.logger.debug(f"Writing content to {output_file}")
            with open(output_file, mode, encoding='utf-8') as f:
                f.write(content)
            self.logger.debug(f"Successfully wrote to {output_file}")
        except PermissionError as e:
             self.logger.error(f"PermissionError writing to report file '{output_file}': {e}")
             raise
        except Exception as e:
             self.logger.error(f"Failed to write to report file '{output_file}': {e}", exc_info=True)