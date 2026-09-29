# Documentation structure

This page states where each piece of this project's documentation belongs and who owns it. It applies to every page in `docs/` and to `README.md`. Read it before adding or moving a page; agents run the `writing-documentation` skill, which applies it step by step.

## The ownership rule

The project is generated from a template, and the template's owner ruled:

> Template owned the designated areas.
> Documentation about domain knowledge can only exist in places designated by the template for [domain] knowledge.
> Documentation about non-domain knowledge is *always* part of the template.
> No exceptions.

**Domain knowledge** belongs to this server alone. It covers the tools, resources and prompts the server offers and how they behave. Its configuration fields and any bundled library count as well. **Non-domain knowledge** is what would be true of any server generated from the template: installing and running it, Docker, systemd, reverse proxies, authentication and identity providers, the security model's frame, configuration mechanics, setting up MCP clients in general, logging, releases, repository protection, template updates and how to contribute.

## Sections

The site is organised by what its reader is trying to do. The template owns this frame, including the order of the sections and the template pages in each; every section except the first two has a slot where this project lists its own pages.

| Section | Reader | Kind of page |
|---|---|---|
| Overview | someone deciding whether this server fits | explanation |
| Security model | anyone asking what the server can reach, change or let in | explanation |
| Get started | a newcomer after a first success | tutorial |
| Deploy | an operator running it for real | how-to |
| Use | someone who runs it and wants more out of it | how-to or explanation |
| Reference | anyone looking a fact up | reference |
| Upgrade | an operator moving to a new release | how-to |
| Contribute | someone changing the project | how-to or explanation |

Moving a template page between sections is a template change. Pages keep their file paths when the frame changes, so their URLs stay the same.

## Where documentation goes

| Place | Owner | Holds |
|---|---|---|
| A template page, outside its sentinel blocks | template | non-domain knowledge only |
| A `DOMAIN-<TOPIC>-<KIND>` block inside a template page (such as the Docker page's extra-notes block) | this project | only what this server adds to that non-domain topic |
| A generated region (`GENERATED-*` markers, such as the configuration tables) | the generator | facts drawn from the code; change the source, never the page |
| `docs/use/` | this project; the template renders only its `index.md` | this server's how-tos and explanations |
| `docs/reference/api/` | this project | API reference, when the project ships a library |
| A section's slot in `nav:` (its `PROJECT-NAV-<SECTION>` block) | this project | entries for this project's pages in that section |
| `docs/releases/` | this project | the per-release notes |
| `docs/design/`, apart from the pages the template renders there | this project | internal design notes, unpublished |

When this project moves one of its own pages, it adds the old and new paths to the redirects map in `mkdocs.yml`, so the published URL keeps working. An entry left under Unsorted at the end of `nav:` hasn't found its section yet.

A sentinel designates a place, not the knowledge in it. Non-domain text inside a `DOMAIN-*` block still belongs to the template.

When no designated place fits domain knowledge, the gap is the template's. File a template issue describing what the content is and who reads it, instead of writing the page somewhere the template doesn't designate. When knowledge is non-domain and the template has no page for it, that also goes to the template as an issue, not into a project page.

A place that departs from this table counts as a decision only when an issue, a pull request or a design note records why. Otherwise it's debt, however settled the file makes it look.

## Each topic has one page

Each topic has one page that answers it. Other pages link to that page and never restate it. A short "you need X; see Y" line is a link, not a copy. When two pages answer the same question, readers get two answers, and one of them goes stale.

Each page is also one kind of text. A tutorial teaches a first success, and a how-to walks through one task. Reference is consulted rather than read; an explanation says why. A page that mixes kinds serves none of its readers well.

## The security model

The [security model](../guides/security-model.md) is the one page that says what the server can reach, what it changes and who gets in. When a page documents a feature that widens that surface, it links there rather than describing the boundary again.

Report a vulnerability as `SECURITY.md` describes, never in a public issue.
