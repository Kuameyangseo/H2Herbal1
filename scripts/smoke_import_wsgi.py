#!/usr/bin/env python3
"""Smoke test: import wsgi and verify attribute 'app' exists and is callable.

Usage:
        python scripts\\smoke_import_wsgi.py

Exit codes:
    0 - success
    2 - import error
    3 - missing attribute
    4 - attribute not callable
"""
from pathlib import Path
import importlib
import sys

def main() -> int:
    # Ensure project root (parent of scripts/) is on sys.path so top-level wsgi.py can be imported
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        mod = importlib.import_module('wsgi')
    except Exception as exc:  # Import failure
        print("IMPORT-ERROR: failed to import module 'wsgi':", exc)
        return 2

    if not hasattr(mod, 'app'):
        print("MISSING-ATTRIBUTE: module 'wsgi' has no attribute 'app'")
        return 3

    app = getattr(mod, 'app')
    if not callable(app):
        print("NOT-CALLABLE: 'app' exists but is not callable")
        return 4

    print("OK: successfully imported 'wsgi.app' and it's callable")
    # Show a short representation for debugging
    print("app repr:", repr(app)[:200])
    return 0


if __name__ == '__main__':
    sys.exit(main())
