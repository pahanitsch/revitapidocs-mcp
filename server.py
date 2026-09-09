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

# Every revitapidocs page id is a SandCastle GUID; anything else is a name.
_GUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Words that name an entity's kind rather than the entity itself; dropped
# before falling back to a single-token query.
_NOISE = {
    "class", "method", "property", "properties", "enumeration", "member",
    "constructor", "interface", "structure", "namespace", "fields", "methods",
    "delegate", "event", "operator",
}

# A blog post file. The two index pages list every post, so they match almost
# any pattern; excluding them here keeps them out of search results.
_POST = re.compile(r"\d{4}_.*\.(md|html?)$", re.IGNORECASE)

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


def _tokens(query: str) -> list[str]:
    """Single-identifier fallbacks for a phrase, most specific first.

    The backend is a prefix matcher over entity names, so "Document.Save" or
    "Document Save Method" match nothing. Retry with the last bare identifier,
    then the first: "Document Save Method" -> "Save" then "Document".
    """
    words = [w for w in re.split(r"[^0-9A-Za-z]+", query) if w]
    core = [w for w in words if w.lower() not in _NOISE] or words
    return list(dict.fromkeys([core[-1], core[0]])) if core else []


def _autocomplete(query: str, limit: int, year: str) -> list[dict]:
    """One raw call to the autocomplete backend, normalized to result dicts."""
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
def search_api(query: str, year: str = "2026", limit: int = 10) -> dict:
    """Search the Revit API for a class, method, property or enum by name.

    Pass a SINGLE identifier, no spaces and no dots: "SaveAsOptions", not
    "Document Save Method" and not "Document.Save". The backend is a prefix
    matcher over entity names, so a phrase or a dotted path matches nothing. To
    reach a member, search its declaring type ("Dimension") and read the member
    list, or search the bare member name ("Save").

    For "how do I ..." questions try search_blog first; use search_api when you
    need the exact class, signature or enum member.

    Returns {"results": [...], "note": <optional>}. Each result's `guid` feeds
    straight into get_doc, and the type is part of the title ("Dimension Class").
    A `note` appears when nothing matched the query verbatim: either the results
    are for a fallback identifier, or there are none and it suggests a rephrase.

    The search index is version-agnostic: `year` only shapes the returned `url`
    and is what get_doc will use. A guid for a member added after `year` can 404
    in get_doc even though it shows up here.

    Args:
        query: one identifier, e.g. "FilteredElementCollector" or "OfCategory".
        year: Revit version, one of 2022-2027 (also "2025.3").
        limit: maximum number of results.
    """
    results = _autocomplete(query, limit, year)
    if results:
        return {"results": results}

    for token in _tokens(query):
        if token == query:
            continue
        results = _autocomplete(token, limit, year)
        if results:
            return {
                "results": results,
                "note": f"no match for {query!r}; showing results for {token!r}",
            }

    return {
        "results": [],
        "note": (
            f"no match for {query!r}; retry with a single identifier such as a "
            f"class name ('Dimension') or a bare method name ('Save')"
        ),
    }


@mcp.tool()
def get_doc(guid: str, year: str = "2026") -> str:
    """Fetch a Revit API documentation page as plain text.

    Args:
        guid: page id from search_api (a GUID), with or without the ".htm"
            suffix. A human-readable name like "Dimension Class" is resolved
            through search_api first; pass a real guid to skip that lookup.
        year: Revit version, one of 2022-2027 (also "2025.3").
    """
    page = guid.removesuffix(".htm")
    note = ""
    if not _GUID.match(page):
        hits = _autocomplete(page, 5, year)
        if not hits:
            raise ValueError(
                f"{guid!r} is not a page id and search found nothing for it; "
                f"call search_api first and pass a guid from its results"
            )
        note = f"(resolved {guid!r} via search to {hits[0]['title']!r})\n\n"
        page = hits[0]["guid"]

    response = _HTTP.get(f"https://www.revitapidocs.com/{year}/{page}.htm")
    response.raise_for_status()
    return note + _text(response.text)


@mcp.tool()
def search_blog(pattern: str, limit: int = 10, context: int = 2) -> list[dict]:
    """Search The Building Coder blog for Revit API techniques and sample code.

    Covers 15 years of posts that rarely surface anywhere else. Reach for this
    first on "how do I ..." questions and for constraints the reference omits
    (e.g. which calls throw when); use search_api for an exact class, signature
    or enum member. Newest posts first.

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
        if not _POST.match(path.name):
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
    hits = search_api("FilteredElementCollector")["results"]
    guid = next(h["guid"] for h in hits if h["title"] == "FilteredElementCollector Class")

    doc = get_doc(guid)
    assert "Autodesk.Revit.DB" in doc, doc[:400]

    # A phrase query must recover through the fallback, not read as empty.
    phrase = search_api("Document Save Method")
    assert phrase["results"] and "note" in phrase, phrase

    # A human-readable name must resolve instead of 404ing upstream.
    named = get_doc("Dimension Class")
    assert "Autodesk.Revit.DB" in named, named[:400]

    posts = search_blog("FilteredElementCollector")
    assert posts and "error" not in posts[0], posts
    assert not any(p["post"].startswith("index") for p in posts), posts

    print(
        f"ok: {len(hits)} api hits, {len(doc)} chars of doc, "
        f"{len(posts)} blog posts, fallback + name-resolve pass"
    )


if __name__ == "__main__":
    _sync_blog()
    if "--check" in sys.argv:
        _self_check()
    else:
        mcp.run()
