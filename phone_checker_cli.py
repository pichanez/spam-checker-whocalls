from phone_spam_checker.cli_base import parse_service_args, run_checker
from phone_spam_checker.registry import register_default_checkers, load_checker_module
from phone_spam_checker.config import settings

register_default_checkers()
for mod in filter(None, getattr(settings, "checker_modules", [])):
    load_checker_module(mod)


def main(argv: list[str] | None = None) -> int:
    service, rest = parse_service_args(argv)
    return run_checker(service, rest)


if __name__ == "__main__":
    raise SystemExit(main())
