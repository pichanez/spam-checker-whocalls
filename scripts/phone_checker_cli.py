from phone_spam_checker.cli_base import parse_service_args, run_checker
from phone_spam_checker.bootstrap import initialize


def main(argv: list[str] | None = None) -> int:
    initialize()
    service, rest = parse_service_args(argv)
    return run_checker(service, rest)


if __name__ == "__main__":
    raise SystemExit(main())
