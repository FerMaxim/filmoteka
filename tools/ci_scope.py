import os
import re
import subprocess
import sys

DOCUMENTS = {
    "AGENTS.md",
    "CHANGELOG.md",
    "KB/ARCHITECTURE.md",
    "KB/AUDIT.md",
    "KB/BACKLOG.md",
    "KB/CATALOG.md",
    "KB/CURRENT_STATE.md",
    "KB/DECISIONS.md",
    "KB/DESIGN.md",
    "KB/ENGINEERING.md",
    "KB/HISTORY_NATIVE.md",
    "KB/HISTORY_PRE_HARNESS.md",
    "KB/LOCAL_DEVELOPMENT.md",
    "KB/OPERATIONS.md",
    "KB/PRODUCT.md",
    "KB/README.md",
    "KB/ROADMAP.md",
    "KB/WORKFLOW.md",
    "KB/TASKS/TEMPLATE.md",
}


def docs_only(paths):
    return bool(paths) and all(
        path in DOCUMENTS or re.fullmatch(r"KB/TASKS/T-[0-9]{3,}\.md", path)
        for path in paths
    )


def classify(base):
    if not base or not re.fullmatch(r"[0-9a-f]{40}", base):
        return "full"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z", base, "HEAD", "--"],
            stdout=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return "full"
    paths = [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]
    if result.returncode == 0 and docs_only(paths):
        return "docs"
    return "full"


if __name__ == "__main__":
    print(f"suite={classify(sys.argv[1] if len(sys.argv) == 2 else None)}")
