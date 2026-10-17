"""Parse sources without importing MicroPython modules or producing pyc files."""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = sorted(p for folder in ("firmware", "examples", "tests", "tools", "ros2_ws/src")
               for p in (root / folder).rglob("*.py"))
for path in files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
print("Syntax OK: {} Python files".format(len(files)))
