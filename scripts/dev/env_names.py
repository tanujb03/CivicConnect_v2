"""Print the variable NAMES of an env file and whether each has an effective value (inline comments do not count). Never prints a value.

    python scripts/dev/env_names.py [path]        # default: .env in the current directory
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def effective(raw: str) -> str:
    v = raw.strip()
    if v.startswith("#"):
        return ""
    return re.sub(r"\s+#.*$", "", v).strip().strip("\"'")


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else ".env")
    if not path.is_file():
        print(f"{path}: not found")
        return 1
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", line)
        if m:
            print(f"{m.group(1)}: {'set' if effective(m.group(2)) else 'empty'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
