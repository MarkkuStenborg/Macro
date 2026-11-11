# ============================================================================
# File: macro_dashboard/cleanup_project.py
# ============================================================================

from pathlib import Path
import shutil

ROOT = Path(__file__).parent

removed = 0

for cache in ROOT.rglob("__pycache__"):
    shutil.rmtree(cache)
    removed += 1
    print(f"REMOVED {cache}")

cache_dir = ROOT / ".cache"

if cache_dir.exists():
    shutil.rmtree(cache_dir)
    removed += 1
    print(f"REMOVED {cache_dir}")

print()
print(f"Removed {removed} items")