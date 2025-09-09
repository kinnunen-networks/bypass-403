import sys

from typing import Optional, List, Dict, Iterable, Union
from urllib.parse import urlparse

from termcolor import colored

from .logger import LoggerManager
from src.config.constants import Constants

"""
Configuration class
"""


class Configuration:
    """
    Args:
    - domain: (str): Domain to target
    - url_file (List[str]): Path to the input url file to process
    - method_file (List[str]): Path to the method file to process
    - header_file (List[str]): Path to the header file to process
    """

    def __init__(
        self,
        domain: str,
        url_file: Optional[str] = None,
        method_file: Optional[str] = None,
        path_file: Optional[str] = None,
        header_file: Optional[str] = None,
    ) -> None:
        """
        Initialize configuration

        Args:
        - domain: (str): Domain to target
        - url_file (List[str]): Path to the input url file to process
        - method_file (List[str]): Path to the method file to process
        - header_file (List[str]): Path to the header file to process
        """

        self.logger = LoggerManager().get_logger()
        self.domain = domain
        self.url_file = url_file
        self.method_file = method_file
        self.path_file = path_file
        self.header_file = header_file

    def load_lines_from_file(self, file_path: str) -> List[str]:
        """
        Read each line from the provided file and return them as a list of strings, with newline characters stripped

        Args:
        - file_path (str): Path to the file to open and read

        Returns:
        - List[str]: A list of line strings
        """

        if not file_path:
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.error(
                f"Couldn't find {file_path}. Check if the file are correctly indexed"
            )
            sys.exit(1)
        except IOError as e:
            self.logger.error(
                f"Something unexpected happened when reading lines from file {e}"
            )
            sys.exit(1)

    def load_paths_from_file(self) -> List[str]:
        """
        Loads path_files from a given file

        Returns:
        - List[str]: A list of path strings
        """

        return self.load_lines_from_file(self.path_file)

    def load_urls_from_file(self) -> List[str]:
        """
        Load lines from a given url file

        Returns:
        - List[str]: A list of url strings
        """

        return self.load_lines_from_file(self.url_file)

    def load_methods_from_file(self) -> List[str]:
        """
        Load lines from a given method file

        Returns:
        - List[str]: A list of method strings
        """

        return self.load_lines_from_file(self.method_file)

    def proxy(self, enable_proxy=False) -> Dict[str, str]:
        """
        Initialize the proxy for inspecting and troubleshooting

        Args:
        - enable_proxy (bool): Whether to enable proxy

        Returns:
        - Dict[str, str]: A dictionary containing the host and HTTP verb
        """

        if enable_proxy:
            proxy_url = f"http://{Constants.proxy_host}:{Constants.proxy_port}"
            return {
                "http": proxy_url,
                "https": proxy_url,
            }
        return {}

    def validate_url(self) -> str | None:
        """
        Ensure the provided URL includes a scheme (http/https) and correct format.
        Adds 'http://' if no scheme provided in the argument.

        Returns:
        - A valid url for further processing.
        """

        if not self.domain:
            return None

        try:
            if not self.domain.startswith(("http://", "https://")):
                url = "http://" + self.domain
            else:
                url = self.domain

            parsed = urlparse(url)

            if not parsed.netloc:
                self.logger.error(f"Invalid domain format: {self.domain}")
                return None

            if parsed.scheme not in ["http", "https"]:
                self.logger.error("Invalid scheme - only http/https allowed")
                return None

            return url

        except Exception as e:
            self.logger.error(f"URL parsing error for {self.domain}: {e}")
            return None

    def load_headers_from_file(self) -> List[Dict[str, str]] | None:
        """
        Loads headers from a file and parses them into key-value pairs

        Returns:
        - A header list stripped and split accordingly to the key and value.
        """

        if not self.header_file:
            return []

        headers_list = []
        try:
            with open(self.header_file, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        headers_list.append({key.strip(): value.strip()})
                    else:
                        self.logger.warning(f"Skipping invalid header line: {line}")
            return headers_list
        except FileNotFoundError:
            self.logger.error(
                f"File not found: {self.header_file}. Check if you provided correct filepath"
            )
            return []
        except IOError as e:
            self.logger.error(
                f"I/O Error occurred when reading {self.header_file}: {e}"
            )
            return []

    def parse_header(self, header_str: str) -> Dict[str, str]:
        """
        Splits a string containing HTTP headers into a list of individual header lines.

        Args:
        - header_str (str): A string containing raw HTTP headers, typically separated by newlines.

        Returns:
        - Dict[str]: A dict of parsed header lines
        """

        try:
            key, value = header_str.split(":", 1)
            return {key.strip(): value.strip()}
        except ValueError:
            self.logger.warning(f"Invalid header format: {header_str}")
            return {}

    def write_results_to_file(
        self, results: List[str], output_file_path: Optional[str] = None
    ) -> None:
        """
        Writes the result to an output file

        Args:
        - results: (List[str]): The list of result strings to write
        - output_file_path (str): Path to the output file where results will be written
        """

        if not results:
            self.logger.warning("No result to write")
            return

        try:
            with open(output_file_path, "w", encoding="utf-8") as f:
                for line in results:
                    f.write(line + "\n")
            self.logger.info(f"Results written to {output_file_path}")
        except IOError as e:
            self.logger.error(
                f"I/O Error occurred when writing to {output_file_path}: {e}"
            )

    @staticmethod
    def color_status_code(status_code: int, line: str) -> str:
        """
        Color the line with the status code to indicate success, failure or so

        Args:
        - status_code (int): the status code of the given line.
        - line: the line of the request result to the web application.

        Returns:
        - str: The line of the request attempt in colored/plain status code format
        """

        if 200 <= status_code < 300:
            return colored(line, "green")
        elif 400 <= status_code < 500:
            if status_code == 404:
                return colored(line, "magenta")
            elif status_code == 429:
                return colored(line, "red", attrs=["bold"])
            else:
                return colored(line, "red")
        elif 500 <= status_code < 600:
            return colored(line, "red", attrs=["bold"])
        else:
            return line

    @staticmethod
    def filter_status(
        results: List[str], status_code: Iterable[Union[int, str]]
    ) -> List[str]:
        """
        Filters the status code based on a provided argument

        Args:
        - results (List[str]): The list of filtered result strings to write
        - status_code (Iterable[Union[int,str]]): An iterable of status code to filter results by

        Returns:
        - List[str]: A list of filtered result strings
        """

        if not results:
            return []

        codes = [str(code) for code in status_code]

        filtered = [r for r in results if any(f"---> {code}," in r for code in codes)]

        return filtered

    @staticmethod
    def format_time_remaining(seconds: float) -> str:
        """
        Format time remaining in a user-friendly way

        Args:
        - seconds: times remaining in seconds
        """

        if seconds <= 0:
            return "0s"
        elif seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            if remaining_seconds > 0:
                return f"{minutes}m {remaining_seconds}s"
            else:
                return f"{minutes}m"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
