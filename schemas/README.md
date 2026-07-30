# Vendored schemas

## `server.schema.json`

The official MCP registry `server.json` schema, vendored so template-ci can
validate a rendered project's `server.json` offline instead of fetching it
over the network on every run.

- Source: `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`
- Version: `2025-12-11` (see the schema's own `$id`)
- Do not hand-edit this file. When `server.json.jinja`'s `$schema` URL bumps
  to a newer dated version, re-fetch the matching schema from the URL above
  (with the new date) and overwrite this file verbatim.

This directory is template-only: `schemas/` is listed in copier.yml's
`_exclude`, so it never renders into a generated project. It exists purely
to back the `jsonschema.validate` checks in
`scripts/tests/test_gen_config_surface.py` and the template-ci gate that
validates the rendered `/tmp/smoke/server.json`.
