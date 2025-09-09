from dataclasses import dataclass

from typing import Optional, List, Union

"""
Runtime configuration
"""


@dataclass
class FuzzerRuntimeConfig:
    max_headers: int
    max_methods: int
    time: int
    delay: float
    num_threads: int
    output_file: Optional[str]
    filter_status_code: Optional[List[Union[int, str]]]
    method: Optional[List[str]]
    header: Optional[str]
    path_batch_size: Optional[int]
    verify_ssl: bool = False
    per_url_time_limit: Optional[float] = None