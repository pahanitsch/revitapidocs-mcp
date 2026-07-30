# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp", "httpx", "truststore"]
# ///
"""MCP server for Revit API docs and The Building Coder blog.

No API keys and no embeddings. API search goes through the public autocomplete
backend that powers revitapidocs.com; blog search greps a sparse clone of
github.com/jeremytammik/tbc that this server clones and pulls on its own.
"""

import os
import re
import ssl
import subprocess
import sys
import time
from html import unescape
from pathlib import Path

import httpx
import truststore
from mcp.server.mcpserver import MCPServer

# The corporate proxy re-signs TLS, so certifi rejects every connection.
# Trust the Windows certificate store instead.
_HTTP = httpx.Client(
    verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
    timeout=30,
    follow_redirects=True,
)

# Public key, lifted from the revitapidocs.com frontend.
_AC_KEY = "key_yyAC1mb0cTgZTwSo"

_REPO = Path(__file__).parent / "tbc"
_TBC = Path(os.environ["TBC_PATH"]) if os.environ.get("TBC_PATH") else _REPO / "a"

mcp = MCPServer("revit-docs")


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True, capture_output=True, timeout=600)


def _sync_blog() -> None:
    """Clone the blog on first start, pull updates on every start after.

    Only the post text is checked out: 45 MB instead of 1.6 GB of images and zips.
    A failure here is not fatal, an existing clone still answers searches.
    """
    if os.environ.get("TBC_PATH"):
        return  # someone else's checkout, not ours to manage
    try:
        # ponytail: pulls on every spawn, cheap enough; gate on FETCH_HEAD mtime if it annoys.
        if _REPO.is_dir():
            _git("-C", str(_REPO), "pull", "--quiet")
        else:
            url = "https://github.com/jeremytammik/tbc.git"
            _git("clone", "--depth", "1", "--filter=blob:none", "--sparse", "--quiet", url, str(_REPO))
            _git("-C", str(_REPO), "sparse-checkout", "set", "--no-cone", "/a/*.md", "/a/*.htm", "/a/*.html")
    except (OSError, subprocess.SubprocessError) as exc:
        # stdout is the JSON-RPC channel, so complain on stderr.
        print(f"blog sync skipped: {exc}", file=sys.stderr)


def _text(html: str) -> str:
    """Strip HTML down to readable text.

    ponytail: regex is enough for these pages; swap in selectolax if it gets noisy.
    """
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    html = re.sub(r"(?i)<(br|/p|/div|/tr|/li|/h[1-6])\s*/?>", "\n", html)
    text = unescape(re.sub(r"(?s)<[^>]+>", " ", html))
    text = re.sub(r"[^\S\n]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


@mcp.tool()
def search_api(query: str, year: str = "2026", limit: int = 10) -> list[dict]:
    """Search the Revit API for classes, methods, properties and enums.

    Returns entries whose `guid` feeds straight into get_doc. The type is part of
    the title, e.g. "FilteredElementCollector Class".

    Args:
        query: entity name or fragment, e.g. "FilteredElementCollector" or "OfCategory".
        year: Revit version, one of 2022-2027 (also "2025.3").
        limit: maximum number of results.
    """
    response = _HTTP.get(
        f"https://ac.cnstrc.com/autocomplete/{query}",
        params={
            "query": query,
            "autocomplete_key": _AC_KEY,
            "num_results": limit,
            "_dt": int(time.time() * 1000),
        },
    )
    response.raise_for_status()
    products = response.json().get("sections", {}).get("Products", [])

    results = []
    for item in products[:limit]:
        data = item.get("data", {})
        page = data.get("url", "")
        results.append(
            {
                "title": item.get("value", ""),
                "guid": page.removesuffix(".htm"),
                "description": data.get("description", ""),
                "url": f"https://www.revitapidocs.com/{year}/{page}",
            }
        )
    return results


@mcp.tool()
def get_doc(guid: str, year: str = "2026") -> str:
    """Fetch a Revit API documentation page as plain text.

    Args:
        guid: page id from search_api, with or without the ".htm" suffix.
        year: Revit version, one of 2022-2027 (also "2025.3").
    """
    page = guid.removesuffix(".htm")
    response = _HTTP.get(f"https://www.revitapidocs.com/{year}/{page}.htm")
    response.raise_for_status()
    return _text(response.text)


@mcp.tool()
def search_blog(pattern: str, limit: int = 10, context: int = 2) -> list[dict]:
    """Search The Building Coder blog for Revit API techniques and sample code.

    Covers 15 years of posts that rarely surface anywhere else. Newest posts first.

    Args:
        pattern: regular expression, case-insensitive.
        limit: maximum number of posts to return.
        context: lines of context to include around each match.
    """
    if not _TBC.is_dir():
        return [{"error": f"no blog clone at {_TBC}; startup sync failed, see the server log"}]

    needle = re.compile(pattern, re.IGNORECASE)
    posts = []
    # Filenames are zero-padded and chronological, so reverse order is newest first.
    for path in sorted(_TBC.iterdir(), reverse=True):
        if path.suffix not in (".md", ".htm", ".html"):
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        hits = [i for i, line in enumerate(lines) if needle.search(line)]
        if not hits:
            continue
        snippets = []
        for i in hits[:5]:
            window = lines[max(0, i - context) : i + context + 1]
            snippets.append(_text("\n".join(window)))
        posts.append(
            {
                "post": path.name,
                "url": f"https://thebuildingcoder.typepad.com/blog/{path.stem}",
                "matches": len(hits),
                "snippets": snippets,
            }
        )
        if len(posts) >= limit:
            break
    return posts


def _self_check() -> None:
    hits = search_api("FilteredElementCollector")
    guid = next(h["guid"] for h in hits if h["title"] == "FilteredElementCollector Class")

    doc = get_doc(guid)
    assert "Autodesk.Revit.DB" in doc, doc[:400]

    posts = search_blog("FilteredElementCollector")
    assert posts and "error" not in posts[0], posts

    print(f"ok: {len(hits)} api hits, {len(doc)} chars of doc, {len(posts)} blog posts")


if __name__ == "__main__":
    _sync_blog()
    if "--check" in sys.argv:
        _self_check()
    else:
        mcp.run()
