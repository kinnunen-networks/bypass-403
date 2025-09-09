from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Iterable, Union

from src.utility.configuration import Configuration

"""
Static configuration
"""


@dataclass
class FuzzerStaticConfig:
    base_url: str
    path_file: List[str]
    url_file: List[str]
    method_file: List[str]
    header_file: List[Dict[str, str]]
    write_results_to_file: Callable[[List[str], str], None]
    header: Optional[Dict[str, str]]
    proxy: Dict[str, str]
    color_status_code: Callable[[int, str], str]
    filter_status: Callable[[List[str], Iterable[Union[int, str]]], List[str]]
    format_time_remaining: Callable[[float], str]

    @classmethod
    def build_fuzzer_config(
        cls, utility: Configuration, header: Optional[str] = None
    ) -> "FuzzerStaticConfig":
        try:
            return FuzzerStaticConfig(
                base_url=utility.validate_url(),
                path_file=utility.load_lines_from_file(utility.path_file) or [],
                url_file=utility.load_lines_from_file(utility.url_file) or [],
                method_file=utility.load_lines_from_file(utility.method_file) or [],
                header_file=utility.load_headers_from_file() or [],
                write_results_to_file=utility.write_results_to_file,
                header=utility.parse_header(header) if header else None,
                color_status_code=utility.color_status_code,
                proxy=utility.proxy(enable_proxy=False) or {},
                filter_status=utility.filter_status,
                format_time_remaining = utility.format_time_remaining
            )
        except (FileNotFoundError, ValueError) as e:
            raise ValueError(f"Failed to build fuzzer config: {e}") from e
