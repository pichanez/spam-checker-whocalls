import argparse
import sys

from phone_spam_checker.infrastructure.kaspersky import main as kaspersky_main
from phone_spam_checker.infrastructure.truecaller import main as truecaller_main
from phone_spam_checker.infrastructure.getcontact import main as getcontact_main

SERVICES = {
    "kaspersky": kaspersky_main,
    "truecaller": truecaller_main,
    "getcontact": getcontact_main,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI for phone spam checking")
    parser.add_argument(
        "service",
        choices=SERVICES.keys(),
        help="Which service implementation to use",
    )
    args, rest = parser.parse_known_args(argv)

    func = SERVICES[args.service]
    old_argv = sys.argv
    sys.argv = [sys.argv[0]] + rest
    try:
        return func()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    raise SystemExit(main())
