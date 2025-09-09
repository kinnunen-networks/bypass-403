import argparse

BANNER = r"""
 _  _    ___ _____   _
| || |  / _ \___ /  | |__  _   _ _ __   __ _ ___ ___
| || |_| | | ||_ \  | '_ \| | | | '_ \ / _` / __/ __|
|__   _| |_| |__) | | |_) | |_| | |_) | (_| \__ \__ \
   |_|  \___/____/  |_.__/ \__, | .__/ \__,_|___/___/
                           |___/|_|
@olofmagn(1.0)
        """


class ArgumentParser:
    """
    Handles argument parsing and script execution
    """

    def __init__(self):
        self.parser = self.create_parser()

    def create_parser(self) -> argparse.ArgumentParser:
        """
        Configures the argument parser with expected arguments.

        Returns:
        - argparse.ArgumentParser: The configured argument parser
        """

        parser = argparse.ArgumentParser(
            description="Bypass 403 to circument different security restrictions",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=BANNER,
        )

        parser.add_argument(
            "-d",
            "--domain",
            type=str,
            help="Domain to test for 403 bypasses"
        )

        parser.add_argument(
            "-l",
            "--url_file",
            type=str,
            help="List of domains to test for 403 bypasses",
        )

        parser.add_argument(
            "-pf",
            "--path_file",
            type=str,
            default="fuzz-data/paths_to_bypass.txt",
            help="File containing the paths to test",
        )

        parser.add_argument(
            "-o",
            "--output_file",
            type=str,
            help="File to write result to (optional)"
        )

        parser.add_argument(
            "-fs",
            "--filter_status_code",
            nargs="+",
            type=int,
            help="Filter HTTP status code(e.g., 200,403)",
            default=[],
        )

        parser.add_argument(
            "-m",
            "--method",
            nargs="+",
            default=None,
            type=str,
            help="HTTP method to use (default: GET)",
        )

        parser.add_argument(
            "-mf",
            "--method_file",
            type=str,
            help="Path to the method file"
        )

        parser.add_argument(
            "-header",
            "--header",
            type=str,
            help="Custom header(s) format: 'Header-Name:value'",
        )

        parser.add_argument(
            "-hf",
            "--header_file",
            type=str,
            required=False,
            help="Path to file containing headers (one per line)",
        )

        parser.add_argument(
            "-mh",
            "--max_headers",
            type=int,
            help="Max headers to iterate the paths with",
        )

        parser.add_argument(
            "-mm",
            "--max_methods",
            type=int,
            help="Max methods to iterate the paths with",
        )

        parser.add_argument(
            "-t",
            "--time",
            type=float,
            default=30,
            help="Max scan in minutes"
        )

        parser.add_argument(
            "-th",
            "--thread",
            type=int,
            default=4,
            help="Number of threads"
        )

        parser.add_argument(
            "-dd",
            "--delay",
            type=float,
            help="Delay between requests"
        )

        parser.add_argument(
            "-bz",
            "--path_batch_size",
            type=int,
            default=100,
            help="Number of paths to process in each batch (default: 100)",
        )

        parser.add_argument(
            "-put",
            "--per-url-time",
            type=float,
            help="Time limit per URL in seconds"
        )

        return parser

    def parse_args(self) -> argparse.Namespace:
        """
        Parse and return command-line arguments

        Returns a namespace object
        """

        return self.parser.parse_args()
