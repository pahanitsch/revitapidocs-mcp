# revit-docs MCP

Look up what the Revit API documentation actually *says* — descriptions, remarks, exceptions — plus 15 years of The Building Coder, from an MCP client. No API keys, no embeddings, no bulk download, and Revit does not have to be installed or running.

| Tool | Does |
|---|---|
| `search_api(query, year, limit)` | find a Revit API class, method, property or enum |
| `get_doc(guid, year)` | fetch a documentation page as plain text |
| `search_blog(pattern, limit, context)` | regex search across 15 years of blog posts |

Pages come from [revitapidocs.com](https://www.revitapidocs.com), with [rvtdocs.com](https://rvtdocs.com) standing in when it is unreachable and covering 2020 and 2021 besides. Two independent sources, because a single undocumented backend is how every earlier Revit docs server died.

## Setup

Needs [uv](https://docs.astral.sh/uv/) and `git`. Clone this repo, then point your MCP client at:

```
uv run --system-certs --script /path/to/server.py
```

That is the whole install. The server clones the blog itself on first start (76 MB of post text, a couple of minutes) and pulls updates on every start after. Run the check below once before wiring it up, so a client's connect timeout does not land on that first clone.

Check it works:

```bash
uv run --system-certs --script server.py --check
```

`--system-certs` lets `uv` reach PyPI where TLS is inspected in transit; the server itself already trusts the operating system's certificate store, which is the right default anywhere. Set `TBC_PATH` to use a blog checkout elsewhere — the server then leaves it alone instead of syncing it.

Blog posts are text only. Roughly half of them carry a screenshot or diagram, so `search_blog` returns the URLs of a post's pictures rather than its bytes: the images weigh 946 MB against 76 MB of text and would not make a single search faster.

## Logging

Off until `REVIT_DOCS_LOG` names a directory to write into. A tool that records what was asked of it should say so before it starts recording, so there is no default-on path.

Two JSON Lines files, appended and never rotated. A call costs a few hundred bytes, so expect kilobytes a month rather than megabytes.

- `calls.jsonl` — one line per call: timestamp, pid, a run id grouping one session's calls, the client's name when it identified itself, tool, the query, result count, which fallback fired, duration, and whether it succeeded.
- `errors.jsonl` — failures only, with exception type, message and traceback. A one-line summary also goes to stderr so the client surfaces it immediately.

Queries are recorded, results are not: a query and a timestamp are enough to replay the call.

## How this differs from dll2llm

Autodesk's [dll2llm](https://github.com/autodesk-platform-services/dll2llm) reflects `RevitAPI.dll` and its neighbouring `RevitAPI.xml` into an Agent Skill: signatures, summaries, remarks and exceptions, generated once and carried in the context window. It is the better answer when you want the whole API offline for the one Revit version you have installed.

This server answers the other shape of the question. It queries live, so one install covers 2020 through 2027 without regenerating anything per version and without Revit being installed at all, and it searches The Building Coder, which no generated skill contains. The two sit together comfortably: a skill for breadth you always carry, a lookup for the page you need right now.

## What is deliberately not here

There is no pyRevit tool. pyRevit's own agent runtime ships `lookup_pyrevit_api`, and measuring before building said not to duplicate it: across 22 sessions that edited pyRevit button bundles, the tool was offered to the model in 15 of them and called in none. Seven of those sessions read `pyrevitlib` sources directly instead and got their answer that way — a longer path, but never a wrong one. Demand existed; a missing tool was not the problem. Should that change, `docs.pyrevitlabs.io` publishes an `llms-full.txt` generated from the same docstrings.
