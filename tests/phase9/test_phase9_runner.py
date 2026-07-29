import sys
from pathlib import Path

from phase9_runner import main as runner_main


def test_runner_validate_help():
    # ensure CLI prints help for validate subcommand when invoked with --help
    try:
        runner_main(["validate", "--help"])  # should exit or print usage
    except SystemExit:
        pass
