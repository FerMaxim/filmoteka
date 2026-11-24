import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[1]
errors = []
for document in [root / "AGENTS.md", *sorted((root / "KB").glob("*.md"))]:
    for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
        target = urlsplit(link)
        if not target.scheme and target.path:
            if not (document.parent / unquote(target.path)).exists():
                errors.append(f"{document.name}: {link}")
if errors:
    raise SystemExit("\n".join(errors))
print("Documentation links OK")
