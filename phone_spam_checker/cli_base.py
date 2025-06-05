import argparse
import logging
from pathlib import Path

# Ensure checkers are registered
from . import infrastructure  # noqa: F401
from .registry import CHECKER_REGISTRY, get_checker_class
from .utils import read_phone_list, write_results
from .logging_config import configure_logging
from .config import settings

logger = logging.getLogger(__name__)


def parse_service_args(argv: list[str] | None = None) -> tuple[str, list[str]]:
    """Parse the service name and return it with the remaining arguments."""
    parser = argparse.ArgumentParser(description="CLI for phone spam checking")
    parser.add_argument(
        "service",
        choices=CHECKER_REGISTRY.keys(),
        help="Which service implementation to use",
    )
    args, rest = parser.parse_known_args(argv)
    return args.service, rest


def parse_common_args(
    argv: list[str] | None = None,
    *,
    description: str = "Phone checker",
) -> argparse.Namespace:
    """Parse common checker arguments."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Input file with phone numbers",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("results.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "-d",
        "--device",
        type=str,
        default="127.0.0.1:5555",
        help="Android device ID",
    )
    return parser.parse_args(argv)


def run_checker(service: str, argv: list[str] | None = None) -> int:
    """Run a checker identified by name with CLI arguments."""
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        log_file=settings.log_file,
    )
    args = parse_common_args(argv, description=f"Phone number lookup via {service}")

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    phones = read_phone_list(args.input)
    logger.info(f"Loaded {len(phones)} numbers from {args.input}")

    checker_cls = get_checker_class(service)
    checker = checker_cls(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]

    checker.close_app()
    write_results(args.output, results)
    logger.info(f"Results saved to {args.output}")
    return 0
