#!/usr/bin/env python3
"""Check local documentation links without Git, network access, or dependencies.

Run ``python scripts/check_docs.py`` from any directory. Only README.md,
AGENTS.md, and Markdown files under docs/ are scanned. Relative destinations
must exist; fragments pointing into Markdown must match a GitHub-style heading
slug or an explicit HTML anchor. External URLs, images, and absolute paths are
outside this check. Use ``--root PATH`` to check another project directory.
"""

import argparse
import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINK_LABEL = re.compile(r"(!?)\[([^\]\n]*(?:\[[^\]\n]*\][^\]\n]*)*)\]")
REFERENCE = re.compile(r"^ {0,3}\[([^\]\n]+)\]:\s*(.+)$", re.MULTILINE)
INLINE_CODE = re.compile(r"(`+)(.*?)\1")


def without_fences(text: str) -> str:
    """Hide fenced code and HTML comments while preserving source line numbers."""
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence):
                fence = None
            lines.append("\n" if line.endswith("\n") else "")
        elif match:
            fence = match[1]
            lines.append("\n" if line.endswith("\n") else "")
        else:
            lines.append(line)
    return re.sub(r"<!--[\s\S]*?-->", lambda m: "\n" * m[0].count("\n"), "".join(lines))


def heading_slug(text: str) -> str:
    """Build a GitHub-style slug, retaining Unicode letters, '-' and '_'."""
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?<!\w)(_+)(.+?)\1(?!\w)", r"\2", text)
    text = html.unescape(text).strip().lower()
    text = "".join(
        char for char in text
        if char in "-_" or not unicodedata.category(char).startswith(("P", "S", "C"))
    )
    return text.replace(" ", "-").strip()


def markdown_anchors(text: str) -> set[str]:
    """Collect heading slugs with GitHub duplicate suffixes and HTML anchors."""
    text = without_fences(text)
    anchors = set()
    counts = {}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+\s*)?$", line)
        heading = match[1] if match else None
        if heading is None and index + 1 < len(lines) and line.strip():
            if re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[index + 1]):
                heading = line.strip()
        if heading is not None:
            slug = heading_slug(heading)
            number = counts.get(slug, 0)
            candidate = slug if number == 0 else f"{slug}-{number}"
            while candidate in anchors:
                number += 1
                candidate = f"{slug}-{number}"
            counts[slug] = number + 1
            anchors.add(candidate)
    for match in re.finditer(r"<[^>]*\b(?:id|name)\s*=\s*['\"]([^'\"]+)['\"][^>]*>", text, re.I):
        anchors.add(html.unescape(match[1]))
    return anchors


def destination(text: str, start: int = 0) -> tuple[str, int] | None:
    """Read an angle path or an unquoted destination with balanced parentheses."""
    index = start
    while index < len(text) and text[index].isspace():
        index += 1
    if index == len(text):
        return None
    if text[index] == "<":
        end = text.find(">", index + 1)
        return (text[index + 1:end], end + 1) if end >= 0 else None
    first = index
    depth = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            index += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        elif char.isspace() and depth == 0:
            break
        index += 1
    return text[first:index], index


def markdown_links(text: str):
    """Yield (source line, destination) for inline and defined reference links."""
    text = INLINE_CODE.sub(lambda m: " " * len(m[0]), without_fences(text))
    references = {}
    for match in REFERENCE.finditer(text):
        value = destination(match[2])
        if value:
            references[" ".join(match[1].split()).casefold()] = value[0]
    consumed_until = 0
    for match in LINK_LABEL.finditer(text):
        if match.start() < consumed_until:
            continue
        end = match.end()
        if text[end:end + 1] == ":":
            continue
        target = None
        if text[end:end + 1] == "(":
            value = destination(text, end + 1)
            if value:
                target = value[0]
                consumed_until = value[1]
        else:
            label = match[2]
            reference = re.match(r"\[([^\]\n]*)\]", text[end:])
            if reference:
                label = reference[1] or label
                consumed_until = end + reference.end()
            target = references.get(" ".join(label.split()).casefold())
        if target is not None and not match[1]:
            yield text.count("\n", 0, match.start()) + 1, target


def check_docs(root: Path) -> int:
    """Check the documentation scope, print counters, and return an exit code."""
    files = [root / name for name in ("README.md", "AGENTS.md") if (root / name).is_file()]
    files.extend(sorted((root / "docs").rglob("*.md")))
    checked = skipped = broken = 0
    anchor_cache = {}
    for source in files:
        for line, target in markdown_links(source.read_text(encoding="utf-8")):
            target = re.sub(r"\\([\\`*{}\[\]()#+.!_<> -])", r"\1", html.unescape(target))
            try:
                parsed = urlsplit(target)
            except ValueError:
                parsed = None
            if parsed and (parsed.scheme or parsed.netloc or unquote(parsed.path).startswith("/")):
                skipped += 1
                continue
            checked += 1
            error = None
            if parsed is None:
                error = "invalid destination"
            else:
                path = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
                if not path.exists():
                    error = "missing file"
                elif parsed.fragment and path.suffix.lower() == ".md":
                    if path not in anchor_cache:
                        anchor_cache[path] = markdown_anchors(path.read_text(encoding="utf-8"))
                    if unquote(parsed.fragment) not in anchor_cache[path]:
                        error = "missing anchor"
            if error:
                broken += 1
                print(f"{source.relative_to(root)}:{line}: {error}: {target}")
    print(f"Documentation: {len(files)} Markdown files, {checked} local links, "
          f"{skipped} external/absolute links skipped, {broken} broken links.")
    return 1 if broken else 0


def main() -> int:
    """Parse the optional project root and run the offline documentation check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Project root to check")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"project root is not a directory: {root}")
    return check_docs(root)


if __name__ == "__main__":
    raise SystemExit(main())
