"""Point the links in README.md, README.fa.md, index.html, site.js and PUBLISHING.md at another GitHub repository.

Usage:  python set-repo.py YourName/YourRepo
"""
import re
import sys
from pathlib import Path

OLD_SLUG = "farrokhzad743-dot/RoutePouNew"
FILES = ("README.md", "README.fa.md", "index.html", "site.js", "PUBLISHING.md")


def pages_host(slug: str) -> str:
    owner, repo = slug.split("/")
    return f"{owner.lower()}.github.io/{repo}"


def main(argv):
    if len(argv) != 2 or not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", argv[1]):
        print("Usage: python set-repo.py YourName/YourRepo")
        return 2
    new = argv[1]
    here = Path(__file__).resolve().parent
    old_pages, new_pages = pages_host(OLD_SLUG), pages_host(new)
    for name in FILES:
        path = here / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = text.replace(OLD_SLUG, new).replace(old_pages, new_pages)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")
            print("updated", name)
    print("Done. Commit and push the changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
