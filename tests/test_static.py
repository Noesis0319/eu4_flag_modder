import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_no_undefined_names():
    """main.py 와 src 의 정의되지 않은 이름 — GUI 경로는 테스트가 못 돌리므로 정적으로 잡는다"""
    pytest.importorskip("pyflakes")
    r = subprocess.run([sys.executable, "-m", "pyflakes", "main.py", "src"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    undefined = [ln for ln in r.stdout.splitlines() if "undefined name" in ln]
    assert undefined == []
