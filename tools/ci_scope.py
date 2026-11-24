import os
import subprocess
import sys
from pathlib import PurePosixPath


def docs_only(paths):
    return bool(paths) and all(
        path in {"AGENTS.md", "CHANGELOG.md"}
        or (PurePosixPath(path).parent == PurePosixPath("KB") and path.endswith(".md"))
        for path in paths
    )


def classify(base):
    if not base:
        return "full"
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", base, "HEAD", "--"],
        stdout=subprocess.PIPE,
        check=False,
    )
    paths = [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]
    if result.returncode == 0 and docs_only(paths):
        return "docs"
    return "full"


if __name__ == "__main__":
    print(f"suite={classify(sys.argv[1])}")
