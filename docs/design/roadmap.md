# fastmcp-server-template roadmap

This is agent-authored synthesis, not a record of decisions. Each item is
tagged `stated` (the account holder's words, with the date), `derived`
(synthesis, revisable at any pass) or `evidenced` (with a locator). Read
the [`roadmapping` skill](../../.agents/skills/roadmapping/SKILL.md) before
charting, refining or revisiting work.

This file is this repository's own index. It never renders: copier renders
`roadmap.md.jinja` beside it into a generated project's seed instead. It
covers the template's epics and packages, and it holds the **family
dependency map**: every edge between this repository, `fastmcp-pvl-core`
and the downstream servers, kept here once. pvl-core's own direction and
packages are argued in
[its index](https://github.com/pvliesdonk/fastmcp-pvl-core/blob/main/docs/design/roadmap.md).

GitHub holds membership, dependencies and progress. This index holds the
argument for the direction and the order, and nothing that GitHub already
tracks.

## Direction

### Domain servers beyond MCP

`stated` (3 November 2026, on pvliesdonk/markdown-vault-mcp#1473): Several
distributions from one repository ship in full lockstep: one version, `==`
cross-pins, one tag, one changelog, one documentation site.

`stated` (4 November 2026): "All servers are mcp servers with a domain
component." "Some, like paperless-mcp are a pure API wrapper. Others
(markdown-vault-mcp/scholar/image generator) have a domain that actually
does something which also makes sense *without* being an mcp server. What
comes to mind is exposing the same domain code as library and/or as a
(non-mcp) rest API and/or a client/server." "We will not need it all in one
bang, which especially holds for this last part." Member names are a
default, not fixed, because of PyPI availability.

`derived`: The template offers fixed roles (library, client, later an
HTTP API) as opt-in workspace members; a wrapper keeps one distribution.
Four epics carry it:

- [#856](https://github.com/pvliesdonk/fastmcp-server-template/issues/856)
  workspace roles, refined into #864 to #869. Its "Done when" is met only
  by a downstream's first two-distribution release, because template-ci
  cannot prove a PyPI publish.
- [#857](https://github.com/pvliesdonk/fastmcp-server-template/issues/857)
  distribution guards: each distribution's independence is a gate.
- [#858](https://github.com/pvliesdonk/fastmcp-server-template/issues/858)
  HTTP API role, after pvl-core's HTTP composition.
- [#859](https://github.com/pvliesdonk/fastmcp-server-template/issues/859)
  reference generation for members.

### Project content in sentinels: [#871](https://github.com/pvliesdonk/fastmcp-server-template/issues/871)

`derived`: Downstreams still write project content into template-owned
lines wherever no seam exists, and every such line conflicts on update.
Members today: #645, #646, #618, #529, #623, #727.

"Done when", as frozen on the epic: "A downstream keeps its project content
for the regions the child issues name inside sentinel blocks, so the
template-conformance check reports no drift there and `copier update`
applies there without conflicts."

Unknown: which `FastMCP()` constructor arguments are domain-owned and which
template-owned. The answer also decides where pvl-core#348's duplicate-name
refusal lives and how pvl-core#350's shared store reaches the constructor.
Resolved by #645's design.

### Per-channel config surface: [#872](https://github.com/pvliesdonk/fastmcp-server-template/issues/872)

`derived`: The config-surface generator decides alone which channel shows
a variable and with what value. Members today: #851, #781, #767, #263.

"Done when", as frozen on the epic: "A project decides, per variable,
which install channels show it (registry manifest, packaged manifests, env
examples, wizard) and with which value, without editing a generated
file."

Unknown: #263 may already be satisfied by the config-contract skill's
wizard hints. Resolved by checking it during refinement; it is cheap.

### One documented Python story: [#873](https://github.com/pvliesdonk/fastmcp-server-template/issues/873)

`derived`: Each channel runs a different Python, the floor moves for the
whole family at once, and the image carries a second interpreter. Members
today: #547, #831, #834.

"Done when", as frozen on the epic: "Each install channel's Python is
documented, and a project can move its own floor without the family moving
with it."

Unknowns:

- The image base. A comment on #831 prefers returning to `python:*-slim`
  once Debian ships a new enough SQLite. Nothing planned resolves that;
  recording it is enough until Debian moves.
- Closing #547 makes pvliesdonk/markdown-vault-mcp#1217's `until:` pin
  fail that project's pin check. Sequence the closure with that pin's
  removal.

### Stacked pull requests that are gated and tested: [#874](https://github.com/pvliesdonk/fastmcp-server-template/issues/874)

`derived`: The `stacking-prs` skill steers work into stacks that the
self-review hook and CI do not fully cover. Members today: #844, #845,
#619.

"Done when", as frozen on the epic: "A stack pushed in one go is
self-review-gated on every branch, and every pull request in it gets CI
while under review."

### Maintenance without an epic

`derived`: These share a theme but no outcome that needs ordering, so
each ships when a package picks it up:

- detach hygiene: #265, #359, #503;
- workflow robustness: #426, #447, #362;
- the Vale gate: #570, #532;
- drift guards: #839, #658;
- shipped-script debt: #666, #723;
- plugin channels: #482, #470, #483;
- observability: #606;
- instruction weight: #768.

## Packages

| Package | Kind | Argument |
|---|---|---|
| [`030 project-seams`](https://github.com/pvliesdonk/fastmcp-server-template/milestone/9) | minor | First: its constructor-ownership decision (#645) settles where two pvl-core fixes live. Its #646 needs pvl-core#355 first, so pvl-core's `005 downstream-fixes` patch ships before this cut or #646 leaves it. |
| [`040 operator-config`](https://github.com/pvliesdonk/fastmcp-server-template/milestone/10) | minor | Before `050`: per-channel exclusion of a variable (#851) is what keeps a client member's variables out of the server's manifests (#868). |
| [`050 workspace-roles`](https://github.com/pvliesdonk/fastmcp-server-template/milestone/11) | minor | Its first real release proves lockstep through knope and the stamp script, which pvl-core's client package (pvl-core#548) then reuses. |
| [`060 distribution-guards`](https://github.com/pvliesdonk/fastmcp-server-template/milestone/12) | minor | After `050`, before a second downstream adopts a role: guards need members to exist. |
| `070 http-api-role` (not created) | minor | After pvl-core's `030 http-composition`; #858 and #859. |

`derived`: #839 (a template-owned build pin that downstream Renovate
moves) blocks a downstream push today and is in `030`, as the current
package. An issue with no milestone is backlog.

## Family dependency map

`evidenced` from issue bodies read on 4 November 2026 unless tagged
otherwise; the locator is the issue. None of these edges is a native
GitHub dependency yet. When they are encoded, this table keeps only what
GitHub cannot hold.

| From | Relation | To |
|---|---|---|
| pvl-core#355 (masked message in `tool_call_failed`) | must ship before | template #646 (mask error details by default) |
| template #645 (constructor seam) | decides the fix location of | pvl-core#348 (duplicate pvl-core tool names), pvl-core#350 (shared request-state store) |
| pvl-core#354 (machine callers under oidc-proxy) | blocks | pvl-core#551 (client auth, service case) |
| template #856 (workspace roles, `050`) | should release before | pvl-core#548 (client package) `derived` |
| pvl-core#548 (client package) | later replaces the transport of | template #868 (client member) `derived` |
| pvl-core#549 (HTTP composition) | blocks | template #858 (HTTP API role) |
| pvl-core#547 (light import) | removes the import cost behind | pvliesdonk/markdown-vault-mcp#2016 |
| template #856 (workspace roles) | blocks | pvliesdonk/markdown-vault-mcp#1473 (package `020` there) |
| template #839 (hatchling pin) | blocks | pvliesdonk/markdown-vault-mcp#1942 |
| template #781 (fixed env entries) | blocks | pvliesdonk/markdown-vault-mcp#1708 |
| template #663 (`py.typed`) | is needed by | pvliesdonk/markdown-vault-mcp#1580 |
| template #547 (Python floor answer) | is the `until:` target of | pvliesdonk/markdown-vault-mcp#1217 |
| pvl-core#349 (elicitation across eras) | blocks | image-generation-mcp#387, #388 |
| pvl-core#362 (search tool catalog) | blocks | pvliesdonk/markdown-vault-mcp#1602 |
| pvl-core#352 (nested claims) | changes the docs of | the template's authorization guide `derived` |
| downstream updates past #713 (scholar, image-generation, openapi, logodev) | unblock | template #723 (retire a migration) |
| PrefectHQ/fastmcp#5263, #5236, #5237 | block | pvl-core#362, #351, #353 |
| anthropics/claude-code-action#1499; Codex plugin env; Claude Code client floor | block | template #447, #483, #470 |

`derived`: How a pvl-core change reaches the fleet:

- A minor within the template's floor and cap arrives by downstream
  Renovate, with no template release.
- A change the template's own code uses needs a floor bump here.
- A new pvl-core variable reaches the generated configuration docs at the
  next `copier update` after the floor moves.
- A major needs this template's cap raised and released. pvl-core#356 is
  the next foreseen one.

## Known unknowns

- `stated` (4 November 2026): The one-repository and synthesis document
  of 29 August 2026 (`docs/superpowers/specs/`) "never led to a satisfying
  conclusion/solution", so its Decision section is unratified. Resolved by
  the account holder. It changes nothing in `030` to `060`. It would change
  where pvl-core#548 is refined, which that epic already notes.
- Whether the deb/rpm channel stays. A comment on #547 doubts it has
  users, and #793 and #842 only matter if it stays. Resolved by the account
  holder; until then both stay in backlog.
- Whether `uv build --all-packages` runs on the uv that `release.yml`
  pins. Resolved by #867.
- Whether scholar-mcp or image-generation-mcp want the roles. Nothing
  planned depends on it, so recording it is enough.

## Revisions

### 4 November 2026: index created

Charted from a triage of every open issue here and in pvl-core. Changes
against the posts of 3 and 4 November on #855 and pvl-core#543:

- **Corrected provenance.** "The HTTP API comes last" is `derived` from
  "this last part"; the wrapper example logo-dev and "a wrapper's only
  value is model-facing shaping" are `derived`, not `stated`.
- **Repository merge.** It is undecided (`stated`), not a ratified
  direction.
- **Proposals awaiting the account holder.** Four epics above are
  proposed, not filed, and so are the package additions #839 and #851.

### 4 November 2026: epics filed, triage applied

`stated` (4 November 2026): "file the epics and create 005, apply the
rest".

- **Epics filed.** The four proposed epics are #871 to #874, with
  refinement issues #875 to #878. Their existing issues are linked as
  sub-issues, and every child kept its milestone.
- **Packages.** #839 joined `030` and #851 joined `040`.
- **Map.** pvl-core#196 closed: a probe shows subpath-aware OAuth
  discovery on fastmcp 4.0.0 and 4.1.6, so its two rows left the map. The
  misplaced `derived` tag on the #856 row moved to the end of the row.
- **Triage applied.** Priorities and areas were set, #150 closed, #263
  narrowed to the undocumented `when`, `secret` and `control` hints, and
  #831 and #768 re-scoped.
- **Not applied.** Whether the deb/rpm channel stays remains a question
  for the account holder.
