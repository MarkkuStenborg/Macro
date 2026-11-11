# ============================================================================
# File: macro_dashboard/add_file_headers.py
# Purpose: Add file path header to all Python files
# ============================================================================

from pathlib import Path

SKIP_DIRS = {
    ".cache",
    "__pycache__",
    ".venv",
    "venv",
    ".git",
}

ROOT = Path(__file__).parent.resolve()

for pyfile in ROOT.rglob("*.py"):

    if any(part in SKIP_DIRS for part in pyfile.parts):
        continue

    rel = pyfile.relative_to(ROOT).as_posix()

    try:
        content = pyfile.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR reading {rel}: {e}")
        continue

    if content.startswith("# =========================================================================="):
        print(f"SKIP {rel}")
        continue

    header = (
        "# ============================================================================\n"
        f"# File: macro_dashboard/{rel}\n"
        "# ============================================================================\n\n"
    )

    try:
        pyfile.write_text(
            header + content,
            encoding="utf-8"
        )
        print(f"UPDATED {rel}")
    except Exception as e:
        print(f"ERROR writing {rel}: {e}")

print("\nDONE")