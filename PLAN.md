# MCP API Bridge — Project Plan

*Created: March 12, 2026*

---

## What This Is

A minimal-but-polished MCP server that wraps a REST API and exposes it as MCP tools — demonstrating the "REST API → MCP server" pattern that Upwork clients are actually posting jobs for. This becomes:

1. **Portfolio demo** in `portfolio/mcp-api-bridge/`
2. **Future Upwork Package 4** candidate (MCP Server Development)
3. **Proof of pattern** that buyers can map to their own API

## Research-Backed Decisions

### Why This Use Case

**Market signal (docs confirm):** Real Upwork job postings for MCP servers are consistently "wrap my existing API/database so AI assistants can use it." Examples found:
- "Build a production-ready MCP server that wraps Unilog CX1 Sigma storefront API"
- "Build a Model Context Protocol Server for SaaS tool"

**Competition is thin:** Only 1 competitor found offering MCP services on Upwork (Mikhail O., integration planning only — not builds). Meanwhile the ecosystem has 18,000+ servers on mcp.so and is growing fast.

**Bryce's moat:** Contributed to Anthropic's Python SDK, built 2 production MCP servers (ContextHub in TypeScript, stylize-mcp-server in Python). This is genuine expertise, not positioning fluff.

### Why JSONPlaceholder as the Demo API

**Decision:** Use [JSONPlaceholder](https://jsonplaceholder.typicode.com) (`/posts` + `/comments` endpoints).

**Rationale:**
- **Zero friction** — no auth, no signup, no rate limits. Buyer clones repo → works immediately
- **Full CRUD** — GET, POST, PUT, PATCH, DELETE all supported
- **Relational data** — posts ↔ comments shows realistic multi-resource patterns
- **Obviously a stand-in** — buyers understand this shows the pattern, not the domain. They imagine their own API in its place
- **Stable** — handles 3B+ requests/month, purpose-built for demos

**Rejected alternatives:**
- GitHub API — requires auth token for useful operations, rate-limited
- OpenWeatherMap/NASA — read-only, can't show CRUD pattern
- Stripe Sandbox — compelling but requires account setup (friction)

### Why Python + FastMCP

**Decision:** Python 3.10+ with FastMCP framework, stdio transport.

**Rationale:**
- Aligns with Bryce's stylize-mcp-server (existing Python MCP experience)
- FastMCP is the recommended framework per MCP Python SDK
- Job postings request "Python or TypeScript" — Python is simpler for demo clarity
- Pydantic v2 for input validation (clean, modern, well-documented)
- stdio transport for local-first simplicity (the right default for a starter kit)

---

## Scope: Minimal But Polished

**Target:** ~400-500 lines of server code, 4 MCP tools, comprehensive README, pytest suite.

### MCP Tools (4 total)

| Tool | Operation | Annotations | Shows Pattern |
|------|-----------|-------------|---------------|
| `api_list_posts` | GET /posts with filtering + pagination | readOnly, idempotent | Pagination, query params, response formatting |
| `api_get_post` | GET /posts/{id} + nested /comments | readOnly, idempotent | Resource lookup, related data joining |
| `api_create_post` | POST /posts | NOT readOnly, NOT idempotent | Write operations, input validation |
| `api_update_post` | PATCH /posts/{id} | NOT destructive, idempotent | Partial updates, existence checks |

**Why these 4:** They cover the four operations every REST API has (list, get, create, update). Delete is omitted intentionally — it's trivial to add but would be a 5th tool that adds length without teaching a new pattern. The README will note this as a deliberate scope decision and show how to add it.

### Tool Design Details

**`api_list_posts`**
- Params: `user_id` (optional filter), `limit` (default 20, max 100), `offset` (default 0), `response_format` (markdown/json)
- Returns paginated results with `has_more`, `next_offset`, `total_count`
- Markdown format shows clean summaries; JSON format returns full objects

**`api_get_post`**
- Params: `post_id` (required), `include_comments` (bool, default false), `response_format`
- Shows the "fetch resource + optional related data" pattern
- When `include_comments=true`, makes 2 API calls and joins results

**`api_create_post`**
- Params: `title` (required, 1-200 chars), `body` (required, 1-5000 chars), `user_id` (required, ≥1)
- Full Pydantic validation with constraints
- Returns the created resource with ID

**`api_update_post`**
- Params: `post_id` (required), `title` (optional), `body` (optional), `user_id` (optional)
- At least one field must be provided (custom validator)
- Shows partial update pattern (PATCH)

### Project Structure

```
portfolio/mcp-api-bridge/
├── README.md              # The showcase — this IS the portfolio piece
├── pyproject.toml          # Modern Python packaging (PEP 621)
├── src/
│   └── api_bridge_mcp/
│       ├── __init__.py
│       ├── server.py       # FastMCP server + tool definitions (~300 lines)
│       └── api_client.py   # Shared HTTP client + error handling (~100 lines)
├── tests/
│   ├── conftest.py         # Shared fixtures, mock API responses
│   ├── test_tools.py       # Tool-level tests (input validation, output format)
│   └── test_client.py      # API client tests (error handling, retries)
└── claude_desktop_config.json  # Example config for Claude Desktop
```

**Why this structure:**
- `src/` layout is Python packaging best practice (PEP 621)
- `api_client.py` separated from `server.py` — shows the pattern of isolating the API layer so buyers understand what they'd swap out for their own API
- `pyproject.toml` over `setup.py` — modern standard
- Example Claude Desktop config removes the "how do I use this?" friction

### Key Architectural Patterns to Demonstrate

1. **Centralized API client** — single `httpx.AsyncClient` with timeout, base URL, headers. Buyers swap this one file to point at their API.
2. **Annotated params with Pydantic Field** — every tool parameter uses `Annotated[type, Field(...)]` for flat schemas with constraints and descriptions. Shows the quality bar.
3. **Dual response format** — markdown for human readability, JSON for programmatic use. MCP best practice.
4. **Consistent error handling** — `_handle_api_error()` utility that maps HTTP status codes to actionable messages.
5. **Tool annotations** — every tool has `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` set correctly.

### README Structure (This Is the Sales Tool)

The README is the single most important file — it's what Upwork buyers and GitHub visitors will actually read.

```
# REST API → MCP Server Bridge

One-line: Turn any REST API into an MCP server for Claude, Cursor, and other AI assistants.

## What This Does (with screenshot/gif of Claude Desktop using the tools)

## Quick Start (3 commands: clone, install, configure)

## How It Works (architecture diagram — simple boxes-and-arrows)

## The Tools (table with name, description, example usage)

## Adapting This For Your API (THE MONEY SECTION)
  - Step 1: Replace api_client.py with your API
  - Step 2: Define your Pydantic input models
  - Step 3: Register your tools
  - Step 4: Update claude_desktop_config.json

## Project Structure (annotated tree)

## Running Tests

## About (link to Bryce's Upwork profile + brycewatson.com)
```

### Test Strategy

**pytest with httpx mocking** — no real API calls in tests.

| Test Category | Count | What It Covers |
|--------------|-------|---------------|
| Input validation | ~6 | Pydantic model constraints (empty strings, out-of-range, missing required) |
| Tool output format | ~4 | Markdown vs JSON format, pagination metadata |
| Error handling | ~4 | 404, 429, timeout, network error |
| API client | ~3 | Base URL construction, headers, timeout config |
| PATCH client | ~2 | PATCH method, payload verification |
| **Total** | **~19 (actual: 46)** | |

Use `pytest-httpx` for clean async mock responses. No real network calls.

---

## Build Plan (Single Session)

| Step | Task | Est. Time |
|------|------|-----------|
| 1 | Scaffold project structure + pyproject.toml | 5 min |
| 2 | Implement `api_client.py` (httpx client + error handler) | 10 min |
| 3 | Implement `server.py` (4 tools with Pydantic models) | 25 min |
| 4 | Write tests (conftest + test_tools + test_client) | 15 min |
| 5 | Run tests, fix issues | 5 min |
| 6 | Write README.md | 15 min |
| 7 | Create claude_desktop_config.json example | 2 min |
| 8 | Update portfolio/README.md table | 2 min |
| 9 | Final review + verify everything runs | 5 min |
| **Total** | | **~85 min** |

## Success Criteria

- [ ] `pip install -e .` works cleanly
- [ ] All 4 tools register and respond to MCP Inspector
- [ ] `pytest` passes with 17+ tests, 0 failures
- [ ] README is self-contained — a developer can go from clone to working in <5 minutes
- [ ] "Adapting This For Your API" section makes the buyer think "I could hire someone to do this for my API"
- [ ] Code follows all MCP best practices from the skill reference (naming, annotations, error handling, pagination)

## Future: Upwork Package 4

Once the demo is solid, this becomes the basis for a new Upwork listing:

**"You will get a Custom MCP Server That Connects AI to Your API"**

| Tier | Price | Scope |
|------|-------|-------|
| Starter | $250 | 3-4 read-only MCP tools wrapping your API. Docs + tests + Claude Desktop config. |
| Standard | $600 | 6-8 tools (read + write). Auth handling. Deployment guide. 1 revision round. |
| Advanced | $1,200 | Full API coverage. Streamable HTTP transport for multi-client. CI/CD pipeline. Loom walkthrough. |

*Pricing follows the same cold-start strategy as Packages 1-2: below industry rates to build reviews, increase 50-75% after 5+ reviews.*

This is deferred — build the demo first, then decide on listing timing.
