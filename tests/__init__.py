"""AFTERPLAY tests. Run from the repository root:

    python -m unittest discover -s tests -t .

The app modules live in src/; importing this package puts src/ on sys.path
before any test module is loaded, also for the portable Python that ignores
PYTHONPATH.
"""
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / 'src')
TESTS = str(Path(__file__).resolve().parent)
# src/ for the app modules; tests/ so a test can reuse helpers from another one
# (for example `from test_automation import window`).
for path in (TESTS, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)
