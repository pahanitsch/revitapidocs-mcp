# revit-docs MCP

Search the Revit API and The Building Coder blog from an MCP client. No API keys, no embeddings.

| Tool | Does |
|---|---|
| `search_api(query, year, limit)` | find a Revit API class, method, property or enum |
| `get_doc(guid, year)` | fetch a documentation page as plain text |
| `search_blog(pattern, limit, context)` | regex search across 15 years of blog posts |

## Setup

Needs [uv](https://docs.astral.sh/uv/) and `git`. Clone this repo, then point your MCP client at:

```
uv run --system-certs --script /path/to/server.py
```

That is the whole install. The server clones the blog itself on first start (45 MB of post text, a couple of minutes) and pulls updates on every start after. Run the check below once before wiring it up, so a client's connect timeout does not land on that first clone.

Check it works:

```bash
uv run --system-certs --script server.py --check
```

`--system-certs` lets `uv` reach PyPI through a TLS-inspecting corporate proxy; the server itself already trusts the system certificate store. Set `TBC_PATH` to use a blog checkout elsewhere — the server then leaves it alone instead of syncing it.
