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

## Logging

Off until `REVIT_DOCS_LOG` names a directory to write into. A tool that records what was asked of it should say so before it starts recording, so there is no default-on path.

Two JSON Lines files, appended and never rotated. A call costs a few hundred bytes, so expect kilobytes a month rather than megabytes.

- `calls.jsonl` — one line per call: timestamp, pid, a run id grouping one session's calls, the client's name when it identified itself, tool, the query, result count, which fallback fired, duration, and whether it succeeded.
- `errors.jsonl` — failures only, with exception type, message and traceback. A one-line summary also goes to stderr so the client surfaces it immediately.

Queries are recorded, results are not: a query and a timestamp are enough to replay the call.
