---
name: writing-documentation
description: >-
  Use before adding, moving or substantially changing a page in docs/ or README.md, or a DOMAIN block in a template docs page: decides whether the knowledge belongs to this project or to the template, which existing page or designated place takes it, and what the change must link to.
---

<!-- ===== TEMPLATE-OWNED — re-rendered on template updates. ===== -->

# Writing documentation

`docs/contribute/docs-structure.md` is the contract: the ownership rule, the places documentation may go, one topic per page, and the security-model link. This skill is the order in which you apply it. When the two appear to disagree, the page wins; don't restate it here.

## 1. Domain or non-domain?

Decide what the knowledge is before deciding where it goes. The test: would it be true of any server generated from the template? Then it's non-domain, and it belongs to the template. Don't write it in this project, not even as a short copy. File it on the template (the `authoring-issues-prs` skill routes it) and link to the template page if one exists.

If you can't decide, say so in the change or the issue with both readings. Don't guess silently.

## 2. Does a page for this topic already exist?

Search `docs/` and `README.md` for the topic before writing. If a page answers the question, change that page. A second page on the same topic is the most common way documentation starts contradicting itself.

## 3. Which place?

For domain knowledge, use the table in the contract page:

- adding to a non-domain topic (a mount, an environment file, a client config for this server): the `DOMAIN-*` block on the template page for that topic;
- a fact the code already holds (a config field, a default): its source, so the generator carries it. Never hand-edit a `GENERATED-*` region;
- release narrative: `docs/releases/`;
- internal design: `docs/design/`.

If none fits, stop and file a template issue for the missing place (step 1's route). Don't create a page the template doesn't designate.

## 4. Links the change owes

- A feature that widens what the server can reach or change links to `guides/security-model.md`, and the security model's domain block says what the feature adds.
- A page that needs another topic links to that topic's page instead of summarising it.

## 5. Examples a reader will paste

- Commands run as shown on macOS's default shell: quote package extras (`"pkg[extra]"`).
- A configuration example says what it configures, and does it: a block labelled read-only sets read-only.
- Code examples run as written against a fresh setup, including any build or init step they depend on.

## 6. Before you finish

- Build the site with `uv run mkdocs build --strict` and run Vale on the changed pages.
- Name the reader the change serves, and what they can now do, in the pull request description.
