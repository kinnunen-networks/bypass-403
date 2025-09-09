
"""
Constants class
"""
from dataclasses import dataclass


@dataclass
class Constants:
    proxy_host = "127.0.0.1"
    proxy_port = "8080"
    TIMEOUT = 10
    MAX_RESULT = 10000
    FILE = "fuzz-data/useragent.txt"
    PROGRESS_LOG_INTERVAL = 100