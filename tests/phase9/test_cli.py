import subprocess
import sys
from pathlib import Path


def test_cli_help_shows_commands():
    # run the CLI help and ensure exit code 0 and known subcommands in output
    repo_root = Path(__file__).resolve().parents[2]
    res = subprocess.run([sys.executable, str(repo_root / "phase9_runner.py"), "--help"], capture_output=True, text=True, cwd=str(repo_root))
    assert res.returncode == 0
    out = res.stdout + res.stderr
    # check for a few subcommands
    assert "discover" in out
    assert "aggregate" in out
    assert "generate-report" in out
    assert "run" in out
