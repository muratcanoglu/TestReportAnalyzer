"""Utility script to verify backend module imports."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if (backend_root_str := str(BACKEND_ROOT)) not in sys.path:
    sys.path.insert(0, backend_root_str)

MODULES_TO_CHECK = [
    "database",
    "parsers.kielt_parser",
    "pdf_analyzer",
    "ai_analyzer",
    "routes",
]


def check_module(module_name: str) -> bool:
    """Try to import a module and report success or failure."""

    try:
        importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - script level feedback
        print(f"✗ {module_name} FAILED: {exc}")
        return False
    else:
        print(f"✓ {module_name} OK")
        return True


def main() -> int:
    """Entry point for the module check script."""

    all_ok = True
    for module_name in MODULES_TO_CHECK:
        all_ok &= check_module(module_name)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
