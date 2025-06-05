from phone_spam_checker.cli_base import parse_service_args, run_checker


def main(argv: list[str] | None = None) -> int:
    service, rest = parse_service_args(argv)
    return run_checker(service, rest)


if __name__ == "__main__":
    raise SystemExit(main())
