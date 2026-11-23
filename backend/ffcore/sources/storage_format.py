"""Confluence storage format (XHTML with `ac:`/`ri:` elements) to Markdown, deterministically.

The converter's input for a Confluence page (plan/16 teknik notlar: "kendi dönüştürücü"): 04's
Markdown path then cleans, gates, chunks and embeds it. Written for FFCore from the plan's rules
(PayCore D1-D5 are rules, not code to copy):

- dropped (navigation, not content): `toc`, `children`, `pagetree`, `recently-updated`,
  `contentbylabel`, `attachments`, `gallery`, `livesearch`, `blog-posts`, images, emoticons;
- `jira` → `JIRA: <KEY>` (the issue is indexed by the Jira source, not copied here);
- `include` / `excerpt-include` → `[Included page: <title>]`, never expanded (the included page
  is indexed itself; expanding would index its text twice);
- `code` / `noformat` → fenced block (CDATA kept as is);
- `info` / `note` / `warning` / `tip` / `panel` → quote, with the macro title when given;
- `expand`, `section`, `column`, `excerpt`, `details` → their body;
- `status` → its title text;
- any other macro: its rich-text body is kept; without a body it is dropped and counted
  (`unknown`), never silently;
- links → their text; tables → Markdown tables (cells flattened to one line); headings, lists,
  emphasis, line breaks kept.
"""

from collections import Counter
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, CData, Comment, NavigableString, Tag

DROPPED = frozenset(
    {
        "toc",
        "toc-zone",
        "children",
        "pagetree",
        "recently-updated",
        "contentbylabel",
        "attachments",
        "gallery",
        "livesearch",
        "blog-posts",
        "anchor",
        "viewfile",
        "profile",
    }
)
CODE = frozenset({"code", "noformat"})
PANELS = frozenset({"info", "note", "warning", "tip", "panel"})
TRANSPARENT = frozenset({"expand", "section", "column", "excerpt", "details", "div", "span"})
INCLUDES = frozenset({"include", "excerpt-include"})
BLOCK = frozenset(
    {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "pre", "blockquote"}
)


@dataclass
class Converted:
    markdown: str
    macros: Counter = field(default_factory=Counter)
    unknown: Counter = field(default_factory=Counter)


def to_markdown(storage: str, *, title: str | None = None) -> Converted:
    """Storage XHTML → Markdown. `title` becomes the H1 when given."""
    # html.parser keeps `ac:`/`ri:` names as written (an XML parser needs the namespaces the
    # storage format never declares) and reads CDATA sections.
    soup = BeautifulSoup(f"<root>{storage}</root>", "html.parser")
    result = Converted(markdown="")
    root = soup.find("root")
    body = _blocks(root, result).strip()
    head = f"# {title.strip()}\n\n" if title and title.strip() else ""
    text = head + body
    result.markdown = _tidy(text) + "\n"
    return result


def _name(tag: Tag) -> str:
    return tag.name


def _param(macro: Tag, name: str) -> str | None:
    for child in macro.find_all("ac:parameter", recursive=False):
        if child.get("ac:name") == name or child.get("name") == name:
            return child.get_text(" ", strip=True) or None
    return None


def _macro_body(macro: Tag) -> Tag | None:
    for child in macro.children:
        if isinstance(child, Tag) and child.name == "ac:rich-text-body":
            return child
    return None


def _plain_body(macro: Tag) -> str | None:
    for child in macro.children:
        if isinstance(child, Tag) and child.name == "ac:plain-text-body":
            return "".join(str(c) for c in child.contents if isinstance(c, NavigableString))
    return None


def _macro(tag: Tag, result: Converted) -> str:
    kind = (tag.get("ac:name") or tag.get("name") or "").strip().lower()
    result.macros[kind] += 1
    if kind in DROPPED:
        return ""
    if kind == "jira":
        key = _param(tag, "key")
        return f"JIRA: {key}" if key else ""
    if kind in INCLUDES:
        page = tag.find("ri:page")
        title = page.get("ri:content-title") if page is not None else None
        return f"\n\n[Included page: {title or '?'}]\n\n"
    if kind in CODE:
        code = _plain_body(tag) or ""
        language = _param(tag, "language") or ""
        return f"\n\n```{language}\n{code.strip(chr(10))}\n```\n\n"
    if kind in PANELS:
        heading = _param(tag, "title")
        body = _macro_body(tag)
        inner = _blocks(body, result).strip() if body is not None else ""
        lines = ([f"**{heading}**", ""] if heading else []) + inner.splitlines()
        quoted = "\n".join(f"> {line}" if line else ">" for line in lines)
        return f"\n\n{quoted}\n\n"
    if kind == "status":
        return _param(tag, "title") or ""
    body = _macro_body(tag)
    if kind in TRANSPARENT or body is not None:
        return _blocks(body, result) if body is not None else ""
    result.unknown[kind] += 1
    return ""


def _inline(node, result: Converted) -> str:
    if isinstance(node, Comment):
        return ""
    if isinstance(node, CData | NavigableString):
        return " ".join(str(node).split()) and _spaced(str(node))
    if not isinstance(node, Tag):
        return ""
    name = _name(node)
    if name in ("ac:structured-macro", "ac:macro"):
        return _macro(node, result)
    if name in ("ac:image", "ac:emoticon", "ri:attachment", "script", "style"):
        return ""
    if name == "ac:link":
        if node.find("ri:user") is not None:
            # A mention: the person's name is not indexed (K-16-0009 S1, R-16-0013 MINOR-3).
            return ""
        body = node.find("ac:link-body") or node.find("ac:plain-text-link-body")
        if body is not None:
            return body.get_text(" ", strip=True)
        target = node.find(True)
        if target is not None:
            return target.get("ri:content-title") or target.get("ri:filename") or ""
        return ""
    if node.name == "br":
        return "  \n"
    text = "".join(_inline(child, result) for child in node.children)
    if node.name in ("strong", "b") and text.strip():
        return f"**{text.strip()}**"
    if node.name in ("em", "i") and text.strip():
        return f"*{text.strip()}*"
    if node.name == "code" and text.strip():
        return f"`{text.strip()}`"
    if node.name == "a":
        return text
    if node.name in BLOCK:
        return "\n\n" + _blocks(node, result) + "\n\n"
    return text


def _spaced(text: str) -> str:
    """Whitespace runs collapsed, keeping one leading/trailing space where the source had one."""
    core = " ".join(text.split())
    lead = " " if text[:1].isspace() else ""
    tail = " " if text[-1:].isspace() else ""
    return f"{lead}{core}{tail}"


def _blocks(node: Tag | None, result: Converted) -> str:
    if node is None:
        return ""
    out: list[str] = []
    for child in node.children:
        if not isinstance(child, Tag):
            out.append(_inline(child, result))
            continue
        name = child.name
        if _name(child) in ("ac:structured-macro", "ac:macro"):
            out.append(_macro(child, result))
        elif name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            text = "".join(_inline(c, result) for c in child.children).strip()
            if text:
                out.append(f"\n\n{'#' * level} {text}\n\n")
        elif name == "p":
            text = "".join(_inline(c, result) for c in child.children).strip()
            if text:
                out.append(f"\n\n{text}\n\n")
        elif name in ("ul", "ol"):
            out.append("\n\n" + _list(child, result, 0) + "\n\n")
        elif name == "table":
            out.append("\n\n" + _table(child, result) + "\n\n")
        elif name == "pre":
            out.append(f"\n\n```\n{child.get_text().strip(chr(10))}\n```\n\n")
        elif name == "blockquote":
            inner = _blocks(child, result).strip()
            out.append("\n\n" + "\n".join(f"> {line}" for line in inner.splitlines()) + "\n\n")
        else:
            out.append(_inline(child, result))
    return "".join(out)


def _list(node: Tag, result: Converted, depth: int) -> str:
    lines = []
    for n, item in enumerate(node.find_all("li", recursive=False), 1):
        marker = f"{n}." if node.name == "ol" else "-"
        own, nested = [], []
        for child in item.children:
            if isinstance(child, Tag) and child.name in ("ul", "ol"):
                nested.append(_list(child, result, depth + 1))
            elif isinstance(child, Tag) and child.name == "p":
                own.append("".join(_inline(c, result) for c in child.children))
            else:
                own.append(_inline(child, result))
        text = " ".join(" ".join(own).split())
        lines.append(f"{'  ' * depth}{marker} {text}")
        lines.extend(nested)
    return "\n".join(lines)


def _cell(cell: Tag, result: Converted) -> str:
    text = " ".join(_blocks(cell, result).split())
    return text.replace("|", "\\|")


def _table(node: Tag, result: Converted) -> str:
    rows = []
    for row in node.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if cells:
            rows.append([_cell(c, result) for c in cells])
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, *body = rows
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _tidy(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank and out:
                out.append("")
            blank = True
            continue
        out.append(line)
        blank = False
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)
