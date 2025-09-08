import concurrent.futures
import random
import threading
import time
import requests

from termcolor import colored
from typing import List
from threading import Semaphore

from config.runtime_config import FuzzerRuntimeConfig
from config.static_config import FuzzerStaticConfig

from utility.logger import LoggerManager
from utility.constants import TIMEOUT, MAX_RESULT, FILE, PROGRESS_LOG_INTERVAL


class Fuzzer:
    """
    Runs the fuzzer engine from the static and runtime config initialization
    """

    def __init__(
        self,
        config: FuzzerStaticConfig,
        runtime_config: FuzzerRuntimeConfig,
    ) -> None:
        self.logger = LoggerManager(__name__).get_logger()
        self.config = config
        self.runtime_config = runtime_config
        self.user_agents = self._load_user_agents()

        self.time_hit_logged = False
        self.stop_event = threading.Event()
        self.log_lock = threading.Lock()
        self.results_lock = threading.Lock()
        self.logged_count = 0

        self.global_time_limit_minutes = runtime_config.time
        self.per_url_time_limit_seconds = getattr(
            runtime_config, "per_url_time_limit", None
        )

        self.scan_start_time = None
        self.current_url_start_time = None

        self._last_request_time = 0
        self._request_timing_lock = threading.Lock()

    # === THREAD PROCESSING METHODS ===

    def _is_per_url_timeout(self) -> bool:
        """
        Check per-URL timeout only

        Returns:
        - bool: True if per-URL timeout
        """

        if (
            self.per_url_time_limit_seconds is not None
            and self.current_url_start_time is not None
        ):
            url_elapsed_seconds = time.time() - self.current_url_start_time
            if url_elapsed_seconds > self.per_url_time_limit_seconds:
                return True
        return False

    def _is_timeout_global(self) -> bool:
        """
        Check global timeout

        Returns:
        - bool: True if elapsed minutes is bigger than global timeout
        """

        if self.stop_event.is_set():
            return True

        current_time = time.time()
        if (
            self.global_time_limit_minutes is not None
            and self.scan_start_time is not None
        ):
            elapsed_minutes = (current_time - self.scan_start_time) / 60
            if elapsed_minutes > self.global_time_limit_minutes:
                self._log_timeout_once(
                    f"Global time limit exceeded: {elapsed_minutes:.2f}min > {self.global_time_limit_minutes}min"
                )
                return True
        return False

    def _coordinate_delay(self, delay: float) -> None:
        """
        Coordinate delay

        Args:
        - delay (float): delay measured in seconds
        """

        if delay is None or delay <= 0:
            return

        with self._request_timing_lock:
            current_time = time.time()
            if self._last_request_time > 0:
                elapsed = current_time - self._last_request_time
                if elapsed < delay:
                    sleep_time = delay - elapsed
                    time.sleep(sleep_time)
                    self._last_request_time = time.time()
                else:
                    self._last_request_time = current_time
            else:
                self._last_request_time = current_time

    # === URL PROCESSING METHODS ===

    def _process_url_list(self) -> List[str]:
        """
        Process multiple URLs from file, applying path testing to each

        Returns:
        - List[str]: Finalized result of iterated urls
        """

        results = []

        for url_index, base_url in enumerate(self.config.url_file, 1):
            self.logger.info(
                f"Starting URL {url_index}/{len(self.config.url_file)}: {base_url}"
            )

            if self._is_timeout_global():
                self.logger.info(f"Global timeout reached, stopping at URL {url_index}")
                break

            self.current_url_start_time = time.time()
            original_base_url = self.config.base_url
            self.config.base_url = base_url.rstrip("/")

            try:
                if self.config.path_file:
                    url_results = self._process_paths_for_base_url()
                else:
                    url_results = self._run_fuzz_threading([self.config.base_url])

                self._log_success(
                    f"Finished URL {url_index}: {len(url_results)} results"
                )
                results.extend(url_results)

            finally:
                self.config.base_url = original_base_url

        return results

    def _process_paths_for_base_url(self) -> List[str]:
        """
        Process paths for base url

        Returns:
        - List[str]: Finalized result of iterated process paths for bash url
        """

        BATCH_SIZE = self.runtime_config.path_batch_size
        results = []

        for i in range(0, len(self.config.path_file), BATCH_SIZE):
            if self._is_timeout_global():
                break
            if self._is_per_url_timeout():
                self.logger.info("Per-URL time limit exceeded")
                break

            batch_paths = self.config.path_file[i : i + BATCH_SIZE]
            batch_urls = []

            for path in batch_paths:
                self._generate_url_variations(path, batch_urls)

            if batch_urls:
                batch_results = self._run_fuzz_threading(batch_urls)
                results.extend(batch_results)

        return results

    # === HTTP REQUEST METHODS ===

    def _run_fuzz_threading(self, urls: List[str]) -> List[str]:
        """
        Run fuzz with actual threading support

        Args:
        - urls: list of URLs

        Returns:
        - List[str]: Finalized result of the request processing threaded
        """

        self.logger.info(f"Starting _run_fuzz_threading with {len(urls)} URLs")

        max_workers = getattr(self.runtime_config, "num_threads", 1)
        if max_workers <= 1:
            return self._run_sequential(urls)

        self.logger.info(f"Using {max_workers} threads for concurrent requests")

        request_semaphore = Semaphore(max_workers)

        all_results = []

        request_tasks = []
        for url in urls:
            for method in self._get_methods():
                for header in self._get_headers():
                    request_tasks.append((url, method, header))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_request = {
                executor.submit(
                    self._make_threaded_request, url, method, headers, request_semaphore
                ): (url, method, headers)
                for url, method, headers in request_tasks
            }

            all_result = self._collect_threaded_result(future_to_request)

        return all_result

    def _collect_threaded_result(self, future_to_request: dict) -> List[str]:
        """
        Collects results from future_to_request

        Args:
        - future_to_request: future result from _run_fuzz_threading

        Returns:
        - List[str]: Finalized result of the request processing threaded
        """

        all_results = []

        for i, future in enumerate(
            concurrent.futures.as_completed(future_to_request), 1
        ):
            self._log_progress(i, len(future_to_request), "Request processing")

            if self._is_timeout():
                for remaining_future in future_to_request:
                    if not remaining_future.done() and remaining_future.cancel():
                        remaining_future.cancel()
                break

            try:
                result = future.result(timeout=1)
                if result and result.strip():
                    with self.results_lock:
                        all_results.append(result)

                    if len(all_results) >= MAX_RESULT:
                        self.logger.warning(f"Result limit ({MAX_RESULT}) exceeded")
                        # Cancel remaining futures
                        for remaining_future in future_to_request:
                            remaining_future.cancel()
                        break

            except concurrent.futures.TimeoutError:
                request_info = future_to_request[future]
                self.logger.warning(
                    f"Future timeout for {request_info[1]} {request_info[0]}"
                )
            except Exception as e:
                request_info = future_to_request[future]
                self.logger.error(
                    f"Future error for {request_info[1]} {request_info[0]}: {e}"
                )

        return all_results

    def _run_sequential(self, urls: List[str]) -> List[str]:
        """
        Original sequential implementation (for when threads = 1)
        """

        all_results = []
        total_requests = len(urls) * len(self._get_methods()) * len(self._get_headers())
        current_request = 0
        start_time = time.time()  # Track start time for estimates

        for url in urls:
            if self._is_timeout():
                break
            for method in self._get_methods():
                if self._is_timeout():
                    break
                for header in self._get_headers():
                    if self._is_timeout():
                        break

                    current_request += 1
                    self._log_progress_with_time(
                        current_request,
                        total_requests,
                        "Request processing",
                        start_time,
                    )

                    if current_request % PROGRESS_LOG_INTERVAL == 0:
                        self._log_global_timeout_remaining()

                    result = self._make_single_request(
                        url, method, header, is_threaded=False
                    )

                    if result:
                        all_results.append(result)
                    if len(all_results) >= MAX_RESULT:
                        self.logger.warning(f"Result limit ({MAX_RESULT}) exceeded")
                        return all_results

        return all_results

    def _make_threaded_request(
        self, url: str, method: str, headers: dict, semaphore: threading.Semaphore
    ) -> str:
        """
        Handle threaded requests with proper delay coordination

        Args:
        - url (str): The URL to request
        - method (str): HTTP method (GET, POST, etc.)
        - headers (dict): HTTP headers to include in the request
        - semaphore (threading.Semaphore): Semaphore to control thread concurrency

        Returns:
        - str: Formatted result string with response details or empty string on timeout
        """

        with semaphore:
            if self._is_timeout():
                return ""

            self._coordinate_delay(self.runtime_config.delay)

            return self._make_single_request(url, method, headers, is_threaded=True)

    def _load_user_agents(self) -> List[str]:
        """
        Load user agents from file

        Returns:
        - List[str]: List of user agents
        """

        try:
            with open(FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.warning(f"{FILE} not found. Using default User-Agents.")
            return [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]

    def _make_single_request(
        self, url: str, method: str, headers: dict, is_threaded: bool = False
    ) -> str:
        """
        Makes a single HTTP request and returns formatted result.

        Args:
        - url (str): The URL to request
        - method (str): HTTP method (GET, POST, etc.)
        - headers (dict): HTTP headers to include in request

        Returns:
        - str: Formatted result string with response details
        """

        if "User-Agent" not in headers:
            headers = headers.copy()
            headers["User-Agent"] = random.choice(self.user_agents)

        if not is_threaded:
            self._coordinate_delay(self.runtime_config.delay)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                verify=self.runtime_config.verify_ssl,
                allow_redirects=True,
                proxies=getattr(self.config, "proxy", None),
                timeout=TIMEOUT,
            )

            result = f"{url} ---> {response.status_code}, {method}, {headers}, {len(response.content)} bytes"

            should_log = True
            if self.runtime_config.filter_status_code:
                should_log = (
                    response.status_code in self.runtime_config.filter_status_code
                )

            if should_log:
                with self.log_lock:
                    self.logged_count += 1
                if self.config.color_status_code:
                    colored_result = self.config.color_status_code(
                        response.status_code, result
                    )
                    self.logger.info(colored_result)
                else:
                    self.logger.info(result)

            return result

        except requests.Timeout:
            self.logger.warning(f"Timeout ({TIMEOUT}s) for {method} {url}")
            return f"{url} ---> TIMEOUT, {method}, {{}}, 0 bytes"

        except requests.ConnectionError as e:
            self.logger.warning(f"Connection failed for {method} {url}: {str(e)[:100]}")
            return f"{url} ---> CONNECTION_ERROR, {method}, {{}}, 0 bytes"

        except requests.RequestException as e:
            self.logger.error(f"Request error for {method} {url}: {str(e)[:100]}")
            return f"{url} ---> ERROR, {method}, {{}}, 0 bytes"

    # === CONFIGURATION HELPERS ===

    def _get_methods(self) -> List[str]:
        """
        Get list of HTTP methods to test

        Returns:
        - List[str]: List of HTTP methods
        """

        if self.runtime_config.method:
            methods = [m.upper() for m in self.runtime_config.method]
        elif self.config.method_file:
            methods = [m.upper() for m in self.config.method_file]
        else:
            return ["GET", "POST", "PATCH", "HEAD"]

        # Apply max_methods limit
        max_methods = getattr(self.runtime_config, "max_methods", None)
        if max_methods is not None and len(methods) > max_methods:
            methods = methods[:max_methods]

        return methods

    def _get_headers(self) -> List[dict]:
        """
        Get list of headers to test.

        Returns:
        - List[dict]: List of header dictionaries for HTTP requests
        """

        if self.config.header:
            headers = [self.config.header]
        elif self.config.header_file:
            headers = self.config.header_file
        else:
            headers = [{}]

        # Apply max_headers limit
        max_headers = getattr(self.runtime_config, "max_headers", None)
        if max_headers is not None and len(headers) > max_headers:
            headers = headers[:max_headers]

        return headers

    def _generate_url_variations(self, path: str, all_urls: List[str]) -> None:
        """
        Generates url variations based on urls and paths

        Args:
        - path (str): string representation of path bypass
        - all_urls (list): A list of all the strings extended
        """

        variations = [
            f"{self.config.base_url}/{path}",
            f"{self.config.base_url}/%2e/{path}",
            f"{self.config.base_url}/{path}/.",
            f"{self.config.base_url}//{path}//",
            f"{self.config.base_url}/./{path}/./",
            f"{self.config.base_url}///{path}///",
            f"{self.config.base_url}/{path}..;/",
            f"{self.config.base_url}/{path};/",
            f"{self.config.base_url}{path}\\*",
            f"{self.config.base_url}/{path}/*",
            f"{self.config.base_url}/{path}%20",
            f"{self.config.base_url}/{path}%09",
            f"{self.config.base_url}/{path.upper()}",
            f"{self.config.base_url}/{path}?",
            f"{self.config.base_url}/{path}/?anything",
            f"{self.config.base_url}/{path}.html",
            f"{self.config.base_url}/{path}.php",
            f"{self.config.base_url}/{path}.json",
        ]
        all_urls.extend(variations)

    def _display_configuration(self) -> None:
        """
        Display detailed fuzzer configuration
        """

        self.logger.info("=" * 50)
        self.logger.info("FUZZER CONFIGURATION")
        self.logger.info("=" * 50)

        # URL info
        if self.config.base_url:
            self.logger.info(f"Target URL: {self.config.base_url}")
        if self.config.url_file:
            self.logger.info(f"URL file: {len(self.config.url_file)} URLs loaded")

        # Path info
        if self.config.path_file:
            self.logger.info(f"Path file: {len(self.config.path_file)} paths loaded")
            self.logger.info(f"Path batch size: {self.runtime_config.path_batch_size}")

        # Method info
        methods = self._get_methods()
        max_methods = getattr(self.runtime_config, "max_methods", None)

        if self.runtime_config.method:
            self.logger.info(f"Methods (runtime): {', '.join(methods)}")
        elif self.config.method_file:
            total_available = len(self.config.method_file)
            methods_used = len(methods)
            if max_methods and total_available > max_methods:
                self.logger.info(
                    f"Methods (file): {methods_used}/{total_available} methods loaded (limited by max_methods)"
                )
            else:
                self.logger.info(f"Methods (file): {methods_used} methods loaded")
        else:
            self.logger.info(f"Methods (default): {', '.join(methods)}")

        # Header info
        headers = self._get_headers()
        max_headers = getattr(self.runtime_config, "max_headers", None)

        if self.config.header:
            self.logger.info(f"Headers (single): {len(headers)} header(s)")
        elif self.config.header_file:
            total_available = len(self.config.header_file)
            headers_used = len(headers)
            if max_headers and total_available > max_headers:
                self.logger.info(
                    f"Headers (file): {headers_used}/{total_available} headers loaded (limited by max_headers)"
                )
            else:
                self.logger.info(f"Headers (file): {headers_used} headers loaded")
        else:
            self.logger.info("Headers: None (empty)")

        # Threading info
        max_workers = getattr(self.runtime_config, "num_threads", 1)

        mode = (
            f"{max_workers} concurrent workers"
            if max_workers > 1
            else "Sequential mode (1 worker)"
        )
        self.logger.info(f"Threading: {mode}")
        if max_workers > 1:
            self.logger.info(f"Estimated speedup: {max_workers}x")

        # Timing info
        delay_display = (
            f"{self.runtime_config.delay}s"
            if self.runtime_config.delay is not None
            else "None"
        )
        self.logger.info(f"Request delay: {delay_display}")
        if self.global_time_limit_minutes:
            self.logger.info(
                f"Global time limit: {self.global_time_limit_minutes} minutes"
            )
        if self.per_url_time_limit_seconds:
            self.logger.info(
                f"Per-URL time limit: {self.per_url_time_limit_seconds} seconds"
            )

        # Other settings
        self.logger.info(f"SSL verification: {self.runtime_config.verify_ssl}")
        self.logger.info(f"Request timeout: {TIMEOUT}s")
        self.logger.info(f"Max results: {MAX_RESULT}")

        if self.runtime_config.filter_status_code:
            self.logger.info(
                f"Status code filter: {self.runtime_config.filter_status_code}"
            )

        if self.runtime_config.output_file:
            self.logger.info(f"Output file: {self.runtime_config.output_file}")

        self.logger.info("=" * 50)

    def _log_progress_with_time(
        self, current: int, total: int, operation: str, start_time: float
    ) -> None:
        """
        Log progress with time

        Args:
        - current (int): current progress count
        - total (int): total progress count
        - operation (str): Scanning progress
        """

        if total > 10:
            interval = max(1, total // 10)
            if current % interval == 0 or current == total:
                percentage = (current / total) * 100
                elapsed_time = time.time() - start_time

                if current > 0:
                    estimated_total_time = elapsed_time * (total / current)
                    time_remaining = estimated_total_time - elapsed_time
                    time_str = self.config.format_time_remaining(time_remaining)

                    self.logger.info(
                        f"{operation} progress: {current}/{total} ({percentage:.1f}%) - "
                        f"Est. {time_str} remaining"
                    )

    # === TIMEOUT MANAGEMENT ===

    def _is_timeout(self) -> bool:
        """
        Single method to check all timeout conditions

        Returns:
        - bool: If time limit is reached
        """

        return self._is_timeout_global() or self._is_per_url_timeout()

    def _log_global_timeout_remaining(self) -> None:
        """
        Log global timeout remaining
        """

        if self.global_time_limit_minutes and self.scan_start_time:
            elapsed_minutes = (time.time() - self.scan_start_time) / 60
            remaining_minutes = self.global_time_limit_minutes - elapsed_minutes

            if remaining_minutes > 0:
                remaining_seconds = remaining_minutes * 60
                time_str = self.config.format_time_remaining(remaining_seconds)
                self.logger.info(f"Global timeout: {time_str} remaining")

    def _log_timeout_once(self, message: str) -> None:
        """
        Log timeout

        Args:
        - message (str): timeout message to log
        """

        with self.log_lock:
            if not self.time_hit_logged:
                self.logger.info(message)
                self.time_hit_logged = True
                self.stop_event.set()

    # === RESULTS PROCESSING ===

    def _log_progress(self, current: int, total: int, operation: str) -> None:
        """
        Log progress at intervals

        Args:
        - current (int): Current progress
        - total (int): Total progress
        - operation (str): Progress operation
        """

        if total > 10:
            interval = max(1, total // 10)
            if current % interval == 0 or current == total:
                percentage = (current / total) * 100
                self.logger.info(
                    f"{operation} progress: {current}/{total} ({percentage:.1f}%)"
                )

    def _log_success(self, message: str) -> None:
        """
        Log a success message in green

        Args:
        - message (str): result message to log
        """

        self.logger.info(colored(message, "green"))

    def _finalize_results(self, results: List[str]) -> List[str]:
        """
        Filter results, write to file, and log summary

        Args:
        - results (List[str]): Raw results from the fuzzing process

        Returns:
        - List[str]: Filtered/unfiltered results list
        """

        self.logger.info(f"Total results before filtering: {len(results)}")

        filtered_results = results
        if self.runtime_config.filter_status_code:
            filtered_results = self.config.filter_status(
                results, self.runtime_config.filter_status_code
            )

            self._log_success(
                f"Results after filtering by status {self.runtime_config.filter_status_code}: "
                f"{len(filtered_results)}"
            )

        # Write results to file
        if self.runtime_config.output_file:
            if filtered_results:
                try:
                    with open(
                        self.runtime_config.output_file, "w", encoding="utf-8"
                    ) as f:
                        for result in filtered_results:
                            f.write(result + "\n")
                    self._log_success(
                        f"Written {len(filtered_results)} results to {self.runtime_config.output_file}"
                    )
                except Exception as e:
                    self.logger.error(f"Error writing to file: {e}")
            else:
                self.logger.info("No results matched filter criteria - no file written")

        # Log execution summary
        if self.runtime_config.filter_status_code and self.logged_count > 0:
            self.logger.info(
                f"Logged during execution: {self.logged_count} results matching "
                f"{self.runtime_config.filter_status_code}"
            )

        return results

    # === MAIN EXECUTION ===

    def run(self) -> List[str]:
        """
        Main execution method that processes URLs and paths

        Returns:
        - List[str]: Finalized result of log and write results
        """

        self.logged_count = 0
        self.scan_start_time = time.time()  # Initialize scan start time

        self._display_configuration()

        results = []

        # Process URL list files
        if self.config.url_file:
            results = self._process_url_list()

        # Process single base URL with paths
        elif self.config.base_url and self.config.path_file:
            results = self._process_paths_for_base_url()

        return self._finalize_results(results)
