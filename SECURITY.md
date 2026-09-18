# Security policy

This file is the template repository's own policy. `SECURITY.md.jinja` next
to it is the one generated projects get; copier's `.jinja` precedence keeps
this file out of renders.

## Reporting a vulnerability

Report it privately through GitHub: open **Security → Report a
vulnerability** on this repository, or go straight to
<https://github.com/pvliesdonk/fastmcp-server-template/security/advisories/new>.
That opens a draft security advisory only you and the maintainers can read.

Do not open a public issue, pull request or discussion for a suspected
vulnerability. If the reporting form is unavailable, open an issue titled
"Security contact request" that says nothing about the finding itself, and a
maintainer replies with a private channel.

## What counts as a vulnerability here

This repository ships files into every project generated from it: the CI,
release and bootstrap workflows, the `Dockerfile`, the packaging manifests,
the server skeleton, the repository rulesets, and the agent instructions.
A flaw in any of them affects every generated project at once, so it is in
scope here even when you found it in a generated project. Examples:

- a workflow that lets pull-request content run with write permissions or
  reach a secret;
- a container image or package layout that runs the server with more
  privilege than it needs, or leaks state between users;
- a default in the config skeleton or the authentication scaffold that is
  unsafe when left unchanged;
- a ruleset or bootstrap change that silently weakens branch protection.

A flaw in `fastmcp-pvl-core` belongs on
[that repository](https://github.com/pvliesdonk/fastmcp-pvl-core/security/advisories/new);
a flaw in a generated project's own domain code belongs on that project.
If you are unsure, report here and the maintainers route it.

## Response targets

The maintainers aim to acknowledge a report within 7 days, to assess it within
30 days, and to publish a fix within 90 days of the report or sooner. A fix
ships as a template release; generated projects receive it through their
scheduled `copier update` pull request, and the advisory says which template
version carries it and whether a manual step is needed (`UPGRADING.md`).

## Supported versions

Only the latest template release is supported. Generated projects pin the
version they were last updated to in `.copier-answers.yml`; a project on an
older version gets the fix by taking the update.

## Disclosure and credit

Disclosure is coordinated: the advisory is published when a fix is available,
or at a date agreed with the reporter. The advisory credits the reporter
unless they ask otherwise. There is no bounty programme.
