"""Create a consistent application backup. Stop the application first."""
import argparse
import os
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent
source = Path(os.environ.get("APP_DATA_DIR", root / "data"))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("operation", choices=["backup", "restore"])
parser.add_argument("path", type=Path)
args = parser.parse_args()
origin, destination = (source, args.path) if args.operation == "backup" else (args.path, source)
if not (origin / "app.sqlite3").is_file():
    parser.error("The source does not contain app.sqlite3.")
if destination.exists():
    parser.error("The destination already exists. Use a new path, or move the existing data aside.")
if origin.resolve() in destination.resolve().parents:
    parser.error("The destination must be outside the source directory.")
shutil.copytree(origin, destination)
print(destination.resolve())
