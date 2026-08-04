import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_local_launcher_check_only_validates_the_project():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "start-dev.ps1"),
            "-CheckOnly",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Validation passed" in result.stdout
