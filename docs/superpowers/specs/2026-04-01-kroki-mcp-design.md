# Kroki MCP Server — Design Spec

## Overview

An MCP server that wraps a self-hosted [Kroki](https://kroki.io/) instance,
exposing diagram rendering as MCP tools. Built by instantiating the
`fastmcp-server-template` into a new repo called `kroki-mcp`.

## Naming

| Item | Value |
|------|-------|
| Repo | `kroki-mcp` |
| Python module | `kroki_mcp` |
| Env prefix | `KROKI_MCP` |
| Human name | Kroki MCP Server |
| CLI command | `kroki-mcp` |

## Architecture

```
LLM Client → MCP Server (kroki-mcp) → httpx.AsyncClient → Self-hosted Kroki
```

The server is a thin stateless HTTP proxy. The service object is an
`httpx.AsyncClient` with `base_url` pointed at the Kroki instance. No
caching, no local diagram processing.

## Configuration

| Env var | Required | Default | Description |
|---------|----------|---------|-------------|
| `KROKI_MCP_BASE_URL` | Yes | — | URL of the self-hosted Kroki instance (e.g. `http://localhost:8000`) |
| `KROKI_MCP_READ_ONLY` | No | `true` | Kept from template; no write tools currently |

`KROKI_MCP_BASE_URL` is validated at startup — the server refuses to start
if it is unset or empty.

## Service Object & Lifespan

**`_server_deps.py`**:

- `make_service_lifespan` creates `httpx.AsyncClient(base_url=config.kroki_base_url, timeout=30.0)`
- Yields it as `{"service": client, "config": config}`
- Closes the client in the `finally` block via `await client.aclose()`

## Tools

### `list_diagram_types`

- **Tags**: none (read-only)
- **Parameters**: none
- **Returns**: list of `{"type": str, "formats": list[str]}` dicts
- **Implementation**: returns a static mapping of Kroki's supported diagram
  types and their valid output formats. Kroki has no discovery endpoint,
  so this is maintained in the server source.

### `render_diagram`

- **Tags**: none (read-only)
- **Parameters**:
  - `diagram_type: str` — e.g. `"plantuml"`, `"mermaid"`, `"graphviz"`
  - `source: str` — the diagram source code
  - `output_format: str = "svg"` — `"svg"` or `"png"`
  - `as_base64: bool = False` — when True and format is PNG, return base64 string instead of MCP Image
- **Behaviour**:
  - Validates `diagram_type` against the known types list
  - Validates `output_format` is supported for that diagram type
  - Calls `POST /{diagram_type}/{output_format}` with `source` as plain text body
  - SVG response: returns the SVG string directly
  - PNG response + `as_base64=False`: returns `fastmcp.Image(data=bytes, format="png")`
  - PNG response + `as_base64=True`: returns the base64-encoded string
  - Surfaces Kroki HTTP errors as readable tool errors

## Resources

### `kroki://health`

- Calls `GET /` on the Kroki instance
- Returns JSON: `{"status": "ok", "kroki_url": "..."}` on success
- Returns JSON: `{"status": "unreachable", "error": "..."}` on failure

## Prompts

### `diagram_helper`

- **Parameter**: `diagram_type: str`
- **Returns**: a prompt with a brief description of the diagram type, a basic
  syntax example, and an instruction to use `render_diagram` to produce output
- **Implementation**: static mapping covering the most popular types
  (PlantUML, Mermaid, GraphViz, D2, DBML, Erd, C4 PlantUML) with a
  generic fallback for others

## Diagram Types Registry

A module-level constant (e.g. `DIAGRAM_TYPES` dict in `_server_tools.py` or a
separate `_diagram_types.py`) mapping each diagram type to its supported output
formats. Used by `list_diagram_types`, `render_diagram` (validation), and
`diagram_helper`. Example structure:

```python
DIAGRAM_TYPES: dict[str, list[str]] = {
    "plantuml": ["svg", "png"],
    "mermaid": ["svg", "png"],
    "graphviz": ["svg", "png"],
    "d2": ["svg", "png"],
    "dbml": ["svg", "png"],
    "ditaa": ["svg", "png"],
    "erd": ["svg", "png"],
    "excalidraw": ["svg", "png"],
    "nomnoml": ["svg", "png"],
    "svgbob": ["svg"],
    "vega": ["svg", "png"],
    "vegalite": ["svg", "png"],
    "wavedrom": ["svg", "png"],
    "bpmn": ["svg", "png"],
    "bytefield": ["svg", "png"],
    "pikchr": ["svg", "png"],
    "structurizr": ["svg", "png"],
    "c4plantuml": ["svg", "png"],
    "tikz": ["svg", "png"],
    "typst": ["svg", "png"],
    "wireviz": ["svg", "png"],
    "symbolator": ["svg", "png"],
    "actdiag": ["svg", "png"],
    "blockdiag": ["svg", "png"],
    "nwdiag": ["svg", "png"],
    "packetdiag": ["svg", "png"],
    "rackdiag": ["svg", "png"],
    "seqdiag": ["svg", "png"],
    "umlet": ["svg", "png"],
}
```

## Error Handling

| Scenario | Source | User-facing message |
|----------|--------|---------------------|
| Kroki unreachable | `httpx.ConnectError` | "Cannot reach Kroki at {url} — is it running?" |
| Diagram syntax error | Kroki HTTP 400 | Pass through Kroki's error text |
| Unknown diagram type | Local validation | "Unknown diagram type '{x}'. Use list_diagram_types to see available types." |
| Unsupported format for type | Local validation | "'{format}' is not supported for '{type}'. Supported: {list}" |
| Timeout | `httpx.TimeoutException` | "Kroki did not respond within 30s" |
| Other Kroki errors | HTTP 5xx | "Kroki returned an error: {status} {text}" |

## Testing

- Mock `httpx.AsyncClient` with `respx`
- Use FastMCP's `mcp.test_client()` for integration-style tests
- Test cases:
  - Successful SVG render
  - Successful PNG render (MCP Image)
  - Successful PNG render (base64 mode)
  - Invalid diagram type → validation error
  - Invalid output format for type → validation error
  - Kroki 400 (syntax error) → error passthrough
  - Kroki unreachable → connection error message
  - Health resource: reachable and unreachable states
  - `list_diagram_types` returns expected structure
  - `diagram_helper` prompt for known and unknown types

## Dependencies

Added to `pyproject.toml` beyond what the template provides:

- `httpx` — added to core `dependencies` (not just extras) since the Kroki
  client needs it at runtime regardless of transport
- `respx` — added to `dev` extra for testing

## Out of Scope

- Caching (stateless proxy; can add later if needed)
- Write tools (Kroki is read-only by nature)
- JPEG/PDF output formats (SVG + PNG covers MCP use cases)
- Authentication to Kroki (self-hosted, assumed on private network)
- GET-based encoded URL rendering (POST is simpler and has no URL length limits)
