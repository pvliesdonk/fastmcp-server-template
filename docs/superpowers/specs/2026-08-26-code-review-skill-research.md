# Provider-neutral code-review skill — research

**Date:** 2026-08-26
**Status:** Research — input to a future design, not a design itself.
**Refs:** #496 (Provider-neutral local code-review skill).
**Builds on:** `2026-08-24-agent-neutral-review-and-release-notes-design.md`
(made hosted review optional, CI the only merge gate, and recorded this skill
as follow-up), `2026-08-25-agent-neutral-instructions-design.md` (the
`.agents/skills/` + `.claude/skills/` symlink portability mechanics).

## 1. Problem

Coding agents push too soon. The failure has two costs:

- **Technical debt lands.** The agent treats "CI is green" as "ready", pushes,
  and the defects CI cannot see (rule violations, contradicted comments,
  reverted intent, plausible-but-wrong logic) reach the PR.
- **The post-push reviewer becomes the peer reviewer.** When a hosted review
  bot is the first real examination a diff gets, every round trip spends the
  *maintainer's* tokens (the template's hosted review runs ~$3/PR per run) and
  every finding costs a public fix-push cycle.

The known local remedy in this fleet is the maintainer's
[preflight-circus](https://github.com/pvliesdonk/claude-plugins/tree/main/plugins/preflight-circus)
plugin: the same examination the post-push bot applies, sat before the push.
It works — "usually worth it" — but it has three problems this research is
about:

1. **Not agent-neutral.** It is built on Claude Code's Workflow tool, model
   pins, worktree isolation, and plugin paths. A contributor driving Codex,
   Gemini CLI, Cursor, or opencode cannot run it at all.
2. **Expensive when it matters least.** A run dispatches 11 lens agents
   (6 core + 5 supplementary when `pr-review-toolkit` is installed) plus one
   scorer agent per raw finding, and any fix round requires a full re-run.
   A clean, prepared diff costs ~11 agents; a finding-heavy round is where
   "roughly forty" comes from. The cost profile is deliberate — cheap when
   the agent prepared, expensive when it didn't — but the mandatory full
   re-run doubles even the prepared path.
3. **Written as a gate, and it frustrates agents.** Verdicts are "permission
   slips" (`clear` / `fix-and-rerun` / `structural`), fixes can be
   "FORBIDDEN", a two-round cap ends in mandated self-criticism, and
   defending a finding is pre-framed as evidence the finding is right. The
   observed result is agents litigating findings and fighting the gate
   instead of fixing the diff — which the reward-hacking literature predicts
   (§5.3).

Issue #496 asks for the repository-owned replacement: one skill a contributor
can invoke with *any* coding agent, that consistently selects the cumulative
PR diff, grounds findings in file:line evidence, distinguishes severity and
confidence, verifies narrowly, preserves unrelated working-tree changes, and
produces output suitable for a PR review or comment — with no dependency on
Claude, model credits, or a required check.

## 2. Requirements extracted from #496 and the approved design

1. Invocable by a contributor's coding agent of choice; no Claude, hosted
   workflow, credit, or status-check dependency.
2. Selects the cumulative pull-request diff (not last-push..HEAD).
3. Findings cite file and line references.
4. Severity and confidence are distinguished, with a shared vocabulary.
5. Targeted verification, not gate re-execution.
6. Unrelated working-tree changes are preserved.
7. Output suitable for a pull-request review or comment.
8. Deterministic CI remains the only merge gate; no ruleset may require an
   agent-review check (invariant 5 of the 2026-08-24 design).

## 3. Prior art I: preflight-circus autopsy

Read in full (`skills/preflight-circus/SKILL.md`, 257 lines;
`workflows/circus.workflow.js`, 1 272 lines). What follows is a keep/drop
inventory for the successor.

### 3.1 Worth keeping

| Element | Why it earned its place |
|---|---|
| **Cumulative range contract**: `BASE = merge-base(HEAD, origin/<derived default branch>)`, never last-push..HEAD; default branch derived, not hardcoded `main` | Matches requirement 2 exactly; the derivation note (a stale `origin/main` resolving an ancient merge-base) is a real failure mode worth carrying verbatim |
| **Lenses = distinct bodies of prior commitment**: rules files, the diff on its own terms, git-history intent, past PR reviews, adjacent comments/docstrings, normative specs | The best taxonomy surveyed anywhere in this research; each lens has crisp flag / don't-flag lists. The *decomposition* survives even if the *parallel dispatch* doesn't |
| **Per-finding evidence field**: verbatim quote with its own file:line (the rule, the commit subject, the comment, the prior review URL) | Requirement 3; also universal across every high-precision tool surveyed (§5.1) |
| **Anchored false-positive rubric + exclusion list**: pre-existing issues, linter/CI-catchable, intentional changes, uncodified opinions, `# noqa`-silenced rules → score 0–25 | The exclusion list is the empirically effective part (§5.1); mirrors the canonical upstream `/code-review` rubric |
| **Coverage honesty**: `examined: full/partial/none` + named blockers; "a clean verdict from a check that never ran is exactly what it exists to catch" | The subtlest and most transferable idea: a clean review must state what was actually examined, and degraded tooling must be loud, not silently green |
| **"Don't reproduce CI"** (shared with `REVIEW.md`) | CI is the deterministic gate; re-running it in review burns tokens to duplicate a stronger check |
| **Args-shape validation before dispatch** (a pasted-through placeholder must abort loudly, not review `undefined..undefined` and report clean) | Generalizes: any step whose silent failure produces a false "clean" needs an explicit guard |

### 3.2 To drop or invert

| Element | Problem | Evidence |
|---|---|---|
| **Gate framing** (verdict machine, forbidden actions, `structural` stop, defense protocol, two-round cap ending in mandated self-diagnosis) | Frames review as an exam the agent has already failed; agents respond by litigating findings ("the pull to work around a finding is the tell that it is right" makes defense unwinnable). Gate-shaped criteria invite gaming rather than fixing | Reward-hacking literature §5.3; the maintainer's own observation that it "managed to frustrate agents" |
| **Mandatory full re-run after any fix** | Doubles cost of every round; the statelessness that motivates it ("I only re-ran lens 1 is impossible") can be had cheaper with targeted re-verification of the changed regions plus one final cheap pass | §5.2: diminishing returns after ~3 rounds; structure beats repetition |
| **Numeric confidence threshold (80) copied into seven prompt bodies** | The file's own HAZARD comment documents the drift trap; numeric self-scores are also model-calibration-dependent, which a provider-neutral skill cannot assume | Greptile: LLM numeric self-rating of its own findings "nearly random" (§5.1); anchored *bands* + exclusion lists are the part that works |
| **Claude-coupled machinery**: Workflow tool, `model: 'sonnet'`/`'haiku'` pins, `isolation: 'worktree'`, `${CLAUDE_PLUGIN_ROOT}`, `agentType: pr-review-toolkit:*`, StructuredOutput schemas | None of it ports (§6.3). The model-pin rationale ("the gate's behaviour has to be a property of the gate, not of the session") is *incompatible in principle* with agent-neutrality — a neutral skill must accept that the bar is applied by whatever model the contributor drives, and compensate with procedure (refutation pass) rather than pinning |
| **Blind parallel dispatch as a requirement** | Only some harnesses can fan out; parallelism must be an optional execution strategy, not the contract | §6.3 |
| **Scorer-agent-per-finding** | An extra dispatch layer whose job (kill false positives) is done at least as well by making the *finder* attempt refutation against the code — the strongest local FP filter surveyed | §5.1, item 4 |

### 3.3 Worth keeping as *norms*, shorn of the moralizing

The circus's "it confirms; it does not discover" ethos — review your own diff
before invoking anything expensive; the pass condition is knowable because
the syllabus (rules files, history, comments) is already open to you — is
correct and belongs in the successor as one calm paragraph, not five sections
of escalation protocol. Likewise the two-round idea survives inverted: not
"you may not continue", but "after two fix rounds, handing the remainder to
the human with a written summary is the *designed* outcome, not a failure".

## 4. Prior art II: the 2026 landscape

Full survey with sources in §8. The short version:

| Tool | Local pre-push? | Agent-neutral? | Notes |
|---|---|---|---|
| CodeRabbit CLI | yes | semi (any agent can invoke it; findings from hosted service, account + network required) | $0.25/file usage pricing; markets itself for agentic loops |
| OpenAI Codex `/review` | yes | no (Codex-only; criteria from repo-owned `AGENTS.md` "Code Review Rules") | GitHub variant posts only P0/P1 |
| Claude Code `/code-review` plugin | yes | no | the circus's canonical upstream; structure in §5.1 |
| Claude `/security-review` | yes | no | open-sourced procedure; hard exclusion lists |
| Cursor BugBot, Graphite, Greptile | no (PR-side) | no | ~$1–1.20/review anchors |
| Qodo PR-Agent (OSS) | partial (CLI, self-host, any LLM key) | closest existing | a *service* you point at a diff, not a procedure your agent follows |
| Gemini CLI code-review extension | yes | no | |

**The niche is open.** Nothing surveyed is simultaneously local, pre-push,
and agent-neutral. The only mechanism that can be all three is the one #496
names: a repository-owned markdown procedure the contributor's own agent
executes. Two vendors validate the adjacent ideas: OpenAI's repo-owned
review-rules-in-`AGENTS.md` precedent (provider-legible criteria, closest
file to the code wins), and CodeRabbit's agentic-loop guidance (hard
3-round cap, crisp exit condition, single-responsibility review passes).

Cost anchors for calibration: commercial reviews land at roughly $0.25–1.20
per review. A single-context local review pass (~one agent turn plus a few
targeted commands) is at market parity; an 11-agent fan-out is several
multiples above it.

## 5. Evidence: what actually controls review quality

### 5.1 False positives are the central problem, and five things work

The base rates are bad everywhere: Greptile's audit of its own product found
~19% of comments valuable and ~79% nits; the best hosted reviewers on
Martian's ~300k-PR benchmark cluster around 50% precision; project-scale LLM
security scanning shows false-discovery rates up to 97%. Filtering is the
design problem. What demonstrably works:

1. **Anchored rubric, high cut.** The canonical `/code-review` plugin anchors
   0–100 to concrete descriptions ("false positive under light scrutiny" /
   "might be a nitpick" / "will be hit in practice") and drops everything
   below 80. The anchors carry the value; a bare numeric self-rating does
   not — Greptile found LLM-as-judge severity scoring of its own output
   "nearly random".
2. **Explicit exclusion lists.** Pre-existing issues, linter/typechecker/CI
   territory, out-of-diff lines, intentional changes, uncodified style
   opinions. Every high-precision tool ships one.
3. **Narrow passes over one broad reviewer.** cubic cut false positives 51%
   without losing recall by replacing a monolithic reviewer with focused
   micro-passes. This vindicates the circus's lens decomposition as
   *charters* — with a caveat that §7.3 inherits: the measured passes were
   independent contexts, so the evidence confounds narrowness of *scope*
   with independence of *judgment*, and no surveyed source separates the
   two. A single context walking narrow charters keeps the first property
   but not the second.
4. **A refutation pass.** Before reporting, re-read the cited file:line and
   try to *disprove* the finding, requiring evidence-typed disagreement
   (cite the code that refutes, or concede). Adversarial-review research
   shows debate only helps when disagreement must cite evidence; refute/
   promote stage-gating is the strongest local FP filter surveyed.
5. **file:line grounding** for every claim — universal among the tools whose
   comments developers actually accept.

### 5.2 Cost: structure beats headcount

Multi-agent pipelines run ~4–15× single-pass tokens (Anthropic's own
numbers; independent measurements range wider). A 3-agent adversarial
structure outperformed a 5-agent baseline in the one controlled comparison
found — adding reviewers has fast-diminishing returns; *how* passes are
structured (find → refute) matters more than how many run. Review is also
input-heavy (5–10:1 input:output), so diff-scoping and targeted file reads
are the main cost levers. The practiced industry cap is ~3 fix-review
rounds, then escalate to a human.

### 5.3 Agent psychology: gates get gamed, contracts get met

Reward hacking around quality gates is well documented (test special-casing,
gaming generalizing into broader misalignment; dedicated benchmarks now
measure it). The actionable phrasing guidance, consistent across Anthropic
and OpenAI material:

- Exit condition = **"every blocking finding fixed or explicitly justified
  in the PR body"** — never "the reviewer approves". Justification is a
  first-class outcome, written for the human, not a "defense" submitted to
  the gate.
- Run review in a **fresh context that sees only the diff and the
  criteria**, not the reasoning that produced the change (self-justification
  bias). For agents without subagents: a separate invocation, or at minimum
  the skill instructing "set aside why you wrote it; read what it says".
- Hard round cap with **human escalation as the designed outcome** — a
  draft-PR-with-notes escape hatch, not a verdict of failure.
- Keep criteria evidence-based so that gaming the review ≈ actually fixing
  the code.

## 6. Portability: what "provider-neutral" can technically mean in 2026

### 6.1 The standard exists and won

Agent Skills (SKILL.md) became an open standard in Dec 2025
([agentskills.io](https://agentskills.io/specification), Linux-Foundation-
adjacent stewardship like AGENTS.md). As of mid-2026, `.agents/skills/<name>/SKILL.md`
is scanned **natively** by OpenAI Codex, GitHub Copilot (CLI, coding agent,
review, VS Code), Gemini CLI, Cursor, opencode, Amp, goose, Zed, Windsurf,
Cline, Roo Code, and ~30 more clients. Claude Code still needs the
`.claude/skills/<name>` symlink — exactly the layout this template already
ships (#486 / the 2026-08-25 design). Several clients (Copilot, Cursor,
opencode, Amp) read `.claude/skills/` too; Claude Code documents symlink
deduplication. Aider is the notable holdout with no native support — an
`AGENTS.md` pointer line ("when reviewing, read `.agents/skills/code-review/SKILL.md`")
is the recognized, if unblessed, fallback, and the template's Skills section
already works this way.

So the delivery mechanism for #496 is *already solved* by template
convention. The remaining neutrality work is inside the file.

### 6.2 Portable surface (safe to use)

- Frontmatter: only the six spec fields — `name` (= directory name),
  `description` (the *only* auto-activation signal most clients use; write
  the triggers into it), optional `license`/`compatibility`/`metadata`.
- Plain markdown body: procedure, checklists, flag / don't-flag lists.
- Prose instructions to run `bash`/`git` commands — every surveyed client
  executes these through its own shell tool.
- Relative `references/*.md` for material that shouldn't load on every
  invocation (spec-sanctioned progressive disclosure; keep SKILL.md under
  ~500 lines / 5k tokens).

### 6.3 Non-portable (must not appear)

- Frontmatter beyond the six fields: `model`, `context: fork`, `agent`,
  `argument-hint`, `disable-model-invocation` (partial), `allowed-tools`
  (in-spec but experimental, ignored by e.g. opencode). Strict validators
  hard-reject unknown keys.
- Body features that arrive as inert literal text elsewhere: `!`command``
  dynamic injection, `@file` attachment, `$ARGUMENTS`/`$N` substitution,
  `${CLAUDE_*}` placeholders, and invocations of Claude-specific tools
  (Task/subagent dispatch, Workflow, SlashCommand).
- Assumed parallel subagents. Phrase fan-out as capability-conditional:
  "if your agent can run isolated subagents, you may run the passes in
  parallel, one per charter; otherwise run them as sequential passes."
- `gh` as a hard dependency. `git` is universal; `gh` (or any GitHub API
  access) gates only the optional past-PR pass and the optional
  post-to-PR output mode, and its absence must degrade to a stated
  limitation, not an error (the coverage-honesty rule).

The circus's model-pinning rationale deserves an explicit burial: a neutral
skill *cannot* make the bar a property of the gate. The compensation is
procedural — the refutation pass and evidence requirements do for any model
what the pin did for one.

## 7. Recommended shape for the skill

The synthesis of §3–§6, stated as recommendations for the future design.

### 7.1 Posture: a review procedure, not a gate

The skill produces a **review artifact**; it never grants or withholds
permission. Its convergence contract:

- Every surviving finding is either **fixed** or **explicitly justified in
  the PR body** (a sentence addressed to the human reviewer — information,
  not a defense submitted for scoring).
- After a fix round, **re-verify the fixed regions narrowly** (the targeted
  checks that confirmed the finding now confirm the fix) instead of
  re-running the whole review; one fresh full pass is warranted only when
  fixes were extensive enough to change the diff's shape.
- After **two fix rounds** with findings still surfacing, stop and hand the
  remainder to the human with the written summary — as the designed
  workflow, in neutral language. (One round below the practiced 3-round
  industry cap, matching the circus's empirical experience that round-two
  failures indicate a preparation or design problem.)

The "prepare first" ethos survives as one paragraph: the review confirms
work already done informally over your own diff; the criteria below are all
derivable from files already open to you, so a clean first pass is the
normal outcome.

### 7.2 Scope contract (mostly inherited from the circus)

- Range: `BASE..HEAD`, `BASE = merge-base(HEAD, origin/<default>)` with the
  default branch derived, never hardcoded; the same cumulative diff every
  post-push reviewer sees.
- **Read-only.** The review changes nothing: no checkouts, no stashes, no
  fixes-while-reviewing. Unrelated working-tree changes are untouched by
  construction (requirement 6). Fixing happens after, as ordinary work.
- **Diff-introduced only.** Pre-existing issues on untouched lines are out
  of scope (the decay-issue pathway exists for those).
- **Don't reproduce CI.** The lint/type/test/audit/prose gate is CI's; the
  review reports nothing those checks gate and re-runs nothing. Shared with
  `REVIEW.md` — see §7.6.
- Verification budget: one targeted command per hypothesis (`REVIEW.md`'s
  "investigate narrowly" norm), plus reading any file at the reviewed revs.

### 7.3 Charters: the lens taxonomy as a sequential checklist

Default execution is **one context walking five charters in order**, each
with flag / don't-flag lists distilled from the circus prompts:

1. **Written rules** — every rules file applicable to the changed files
   (`AGENTS.md` tree, `REVIEW.md` domain block, `CONTRIBUTING.md`): explicit
   reviewable rules only.
2. **The diff on its own terms** — logic errors, missing None-handling,
   leaks, swallowed exceptions, security sinks visible in the hunks.
3. **Adjacent commitments** — comments, docstrings, and invariant markers in
   the full files at HEAD that the hunks contradict or make stale.
4. **Recorded intent** — `git log`/`git blame` on touched regions:
   re-introduced fixed patterns, silently reverted fixes, contradicted
   stated intent. Cheap (local git only).
5. **Normative conformance** — only when the diff touches schemas or
   RFC-2119 prose: testability, keyword discipline, executed-instance
   checks. Self-check applicability first; "not applicable" is the normal
   outcome.

An optional sixth charter, **past PR reviews**, runs only when GitHub API
access is available and the diff touches files with recent review history —
the circus's most expensive, lowest-yield lens becomes conditional.

Capability-conditional parallelism per §6.3. This cuts the mandatory cost
from 11 dispatches to ~1 while keeping each charter narrow — but per
§5.1(3)'s caveat, a shared context retains only the narrow *scope* of the
measured micro-pass designs, not their independent *judgment*: an earlier
charter's rubric can color a later charter's reading. Whether the
sequential form keeps enough of the benefit is precisely what the trial
prerequisite (§7.9) must measure, on this degraded path specifically.

### 7.4 Two phases: find, then refute

Phase 1 over-collects candidate findings against the charters. Phase 2 — the
replacement for the scorer fleet — takes each candidate and **attempts to
refute it**: re-read the cited lines in full context, check the exclusion
list (pre-existing? linter territory? intentional? silenced with rationale?),
run at most one targeted command where execution can settle it. Only findings
that survive refutation are reported, each carrying what was checked. In a
harness with subagents, phase 2 is where a fresh context earns its cost
(§5.3's self-justification bias); single-context agents get an explicit
"switch sides: your job is now to disprove each item" instruction. That
fallback must be named for what it is: the weakest form of the mitigation,
in exactly the setup §5.3's literature identifies as most biased — the
same context that wrote the diff judging its own findings — and it is the
*common* case across target agents (§6.3: most harnesses offer no
subagent fork the skill can rely on). The design cannot assume this path
away; it must measure it (§7.9).

### 7.5 Vocabulary: severity × confidence, words not numbers

Two orthogonal axes on every finding:

- **Severity** — `blocker` (correctness, security, data-loss, or an explicit
  written rule violated) / `important` (will bite later; contradicted
  commitments, docstring rot, missing error handling) / `minor` (worth a
  line, never worth a round). Report blockers and importants; minors only
  aggregated or on request — aligning with `REVIEW.md`'s converge rule and
  Codex's P0/P1-only precedent.
- **Confidence** — `verified` (confirmed by executing something or by the
  quoted evidence directly) / `plausible` (survived refutation but rests on
  reading, not execution). Anchored *bands* rather than a 0–100 threshold:
  the words carry their own anchors across models, and there is no numeric
  constant to drift across prompt copies (the circus's own documented
  HAZARD).

### 7.6 Output shape

A markdown findings block designed to be pasted whole into a PR comment or
kept in the PR body:

- Header: range reviewed (`BASE..HEAD` SHAs), charters walked, and any
  **coverage limitation** stated plainly ("no GitHub API access; past-PR
  charter skipped") — the coverage-honesty rule, in prose instead of enum.
- Per finding: `file:line` — severity/confidence — one-sentence defect —
  verbatim evidence with its own citation — suggested fix — and, after a fix
  round, its resolution (`fixed in <sha>` / justification text).
- A clean review states what was examined, never a bare "LGTM".

The block is the artifact requirement 7 asks for; posting it to the PR
(via `gh` or the agent's own integration) is an optional last step, never
required for the skill to complete.

### 7.7 Integration into the template

- `.agents/skills/code-review/SKILL.md` + `.claude/skills/code-review`
  symlink; name registered in the three lockstep places (`TEMPLATE_SKILLS`,
  `test_shared_skill_paths.py`, the `copier.yml` before-stage guard).
- One line in `AGENTS.md`'s Skills section ("before opening, readying, or
  updating a PR — self-review the cumulative diff"), doubling as the Aider
  fallback pointer. Keeps the always-loaded budget flat.
- **Shared norms with hosted review.** `REVIEW.md` (consumed by the optional
  hosted reviewer) and this skill overlap on don't-reproduce-CI, investigate
  narrowly, focus, and converge. Recommendation: the skill *reads*
  `REVIEW.md` as its charter-1 input — including the `DOMAIN-REVIEW`
  sentinel, so a project writes its review rules once and both the local
  skill and the hosted bot honor them. The alternative (duplicating norms
  into the skill with a lockstep test) adds a guard where a read suffices.
- Probably `.jinja`: at minimum the structural-gate and hosted-review
  variants change what "CI already covers" and "the post-push reviewer"
  mean; render variants and hygiene coverage follow the existing rules.
- Template-repo dogfooding: the template repo itself can carry the same
  skill (it already carries `authoring-issues-prs` verbatim), pointed at
  `template-ci`'s job names instead of the rendered `ci.yml`.

### 7.8 Cost target

Default invocation ≈ one agent context + a handful of targeted commands —
at parity with commercial per-review pricing ($0.25–1.20) rather than
multiples of it. The optional parallel mode and the conditional past-PR
charter are the only multipliers, both opt-in. This is the property that
makes "run it before every PR-bound push" a sustainable ask rather than the
circus's exam-you-must-book.

### 7.9 Prerequisite: measure the degraded path before the design freezes

The release-notes skill was hardened by recorded trial runs (#347); this
skill needs the same, and not as after-the-fact verification but as a
**prerequisite to freezing the charter prompts**: run the drafted procedure
over a handful of historical PRs with known post-push findings and measure
what it catches, misses, and invents. The measurement that matters is the
**single-context, no-subagent path** — the common case across target
agents, and the one whose effectiveness the surveyed evidence does not
establish (§5.1(3)'s scope-vs-independence caveat; §7.4's weakest-form
refutation fallback). "Provider-neutral" must mean *effective on most
providers*, not merely *runnable on most providers*; the trial is the only
way to know which one the sequential-charter form delivers, and its outcome
may legitimately change the recommended shape (for example, requiring a
second invocation for the refutation phase where no subagent exists).

## 8. Open questions for the design

1. **Severity taxonomy final form** — the three-level vocabulary above vs
   [Conventional Comments](https://conventionalcomments.org/) labels
   (machine-parseable, mildly novel for an AI reviewer, but heavier).
2. **Where findings land by default** — PR body section vs posted PR
   comment; and whether the fix-round resolution log is part of the
   committed PR description.
3. **REVIEW.md relationship** — charter-1-reads-REVIEW.md (recommended
   above) vs merging `REVIEW.md` into the skill and pointing the hosted
   workflow at the skill instead. The latter is cleaner long-term but
   touches the hosted-review workflow this design was scoped away from.
4. **Trial-run mechanics** — the trial itself is a prerequisite, not an
   open question (§7.9); open are only its mechanics: which historical PRs
   form the benchmark set, and how catches, misses, and inventions are
   recorded and compared across harnesses.
5. **Windows contributors** — the symlink caveat already noted in the
   instructions design applies unchanged.
6. **A `security-review` sibling** — the hard-exclusion-list pattern from
   Anthropic's open-sourced security procedure ports the same way; out of
   scope for #496 but the charter structure should not preclude it.

## 9. Sources

Preflight-circus: [plugin](https://github.com/pvliesdonk/claude-plugins/tree/main/plugins/preflight-circus)
(SKILL.md + circus.workflow.js read in full).

Standards and portability:
[Agent Skills specification](https://agentskills.io/specification) ·
[client showcase](https://agentskills.io/clients) ·
[implementation guide](https://agentskills.io/client-implementation/adding-skills-support) ·
[Codex skills](https://developers.openai.com/codex/skills/) ·
[Copilot agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) ·
[Gemini CLI skills](https://geminicli.com/docs/cli/skills/) ·
[Cursor skills](https://cursor.com/docs/context/skills) ·
[opencode skills](https://opencode.ai/docs/skills/) ·
[Amp](https://ampcode.com/manual#agent-skills) ·
[Zed](https://zed.dev/docs/ai/skills) ·
[Cline](https://docs.cline.bot/customization/skills) ·
[Windsurf](https://docs.windsurf.com/windsurf/cascade/skills) ·
[Claude Code skills (symlinks, frontmatter portability)](https://code.claude.com/docs/en/skills) ·
[AGENTS.md](https://agents.md/).

Tools and practices:
[code-review plugin source](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md) ·
[claude-code-security-review](https://github.com/anthropics/claude-code-security-review) ·
[CodeRabbit CLI](https://docs.coderabbit.ai/cli) ·
[CodeRabbit loop engineering](https://www.coderabbit.ai/blog/loop-engineering) ·
[Codex custom review rules](https://developers.openai.com/blog/custom-code-review-rules-for-codex) ·
[gemini-cli code-review extension](https://github.com/gemini-cli-extensions/code-review) ·
[Anthropic best practices](https://code.claude.com/docs/en/best-practices).

Evidence base:
[Greptile, "How to make LLMs shut up"](https://www.greptile.com/blog/make-llms-shut-up) ·
[cubic micro-agent learnings](https://www.cubic.dev/blog/learnings-from-building-ai-agents) ·
[Adversarial Review (arXiv 2608.18167)](https://arxiv.org/html/2608.18167) ·
[Refute-or-Promote (arXiv 2604.19049)](https://arxiv.org/pdf/2604.19049) ·
[SWR-Bench (arXiv 2509.01494)](https://arxiv.org/html/2509.01494v1) ·
Martian AI-code-review benchmark (via
[CodeRabbit](https://www.coderabbit.ai/blog/coderabbit-tops-martian-code-review-benchmark) /
[cubic](https://www.cubic.dev/blog/cubic-is-the-best-ai-code-reviewer-on-martian-s-benchmark) writeups) ·
[EvilGenie reward-hacking benchmark (arXiv 2511.21654)](https://arxiv.org/html/2511.21654v2) ·
[Conventional Comments](https://conventionalcomments.org/).

Claims from secondary sources that were not independently verified are
marked in the survey agents' raw findings; the load-bearing claims above
(spec fields, per-client skill discovery paths, plugin rubric and threshold,
circus mechanics) were verified against primary sources or read directly
from source code.
