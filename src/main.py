import logging
import sys
import urllib3

from src.config.runtime_config import FuzzerRuntimeConfig
from src.config.static_config import FuzzerStaticConfig

from src.utility.argumentparser import ArgumentParser
from src.utility.logger import LoggerManager
from src.utility.configuration import Configuration

from src.bypass_403 import Fuzzer

logger = LoggerManager(__name__).get_logger()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class App:
    def __init__(self):
        """
        Initialize the application, including argument parsing and runner
        """

        parser = ArgumentParser()
        args = parser.parse_args()

        if not args.domain and not args.url_file:
            logging.error(
                "Error: You must provide either -d (domain) or -l (list of domains)"
            )
            sys.exit(1)

        configuration = Configuration(
            domain=args.domain,
            url_file=args.url_file,
            method_file=args.method_file,
            path_file=args.path_file,
            header_file=args.header_file,
        )
        config = FuzzerStaticConfig.build_fuzzer_config(configuration, args.header)
        runtime_config = FuzzerRuntimeConfig(
            max_headers=args.max_headers,
            max_methods=args.max_methods,
            time=args.time,
            delay=args.delay,
            output_file=args.output_file,
            filter_status_code=args.filter_status_code,
            method=args.method,
            header=args.header,
            num_threads=args.thread,
            path_batch_size=args.path_batch_size,
            per_url_time_limit=args.per_url_time,
        )

        self.fuzzer = Fuzzer(config=config, runtime_config=runtime_config)

    def run(self):
        """
        Runs the main logic for the script execution
        """

        self.fuzzer.run()


def main():
    """
    The entry point for script execution
    """

    try:
        app = App()
        app.run()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
