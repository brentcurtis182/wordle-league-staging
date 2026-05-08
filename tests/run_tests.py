#!/usr/bin/env python3
"""
WordPlayLeague Regression Test Runner

Usage:
    python tests/run_tests.py                                           # staging (default)
    python tests/run_tests.py --base-url https://app.wordplayleague.com # prod
    python tests/run_tests.py --headed                                  # watch in browser
    python tests/run_tests.py -k test_player                            # run specific tests
    python tests/run_tests.py tests/test_auth.py                        # run one file
"""

import subprocess
import sys


def main():
    args = ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]

    # Pass through all CLI args to pytest
    args.extend(sys.argv[1:])

    # Default base URL if not specified
    if not any("--base-url" in a for a in sys.argv):
        args.extend(["--base-url", "https://staging.wordplayleague.com"])

    print(f"\n{'='*60}")
    print(f"  WordPlayLeague Regression Tests")
    print(f"  Command: {' '.join(args)}")
    print(f"{'='*60}\n")

    result = subprocess.run(args)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
