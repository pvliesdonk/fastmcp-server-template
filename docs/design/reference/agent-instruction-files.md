---
type: Reference
title: Agent instruction files
description: What vendors, the AGENTS.md steward and the published studies say about what belongs in an always-loaded instruction file or an on-demand skill, how length and instruction count affect adherence, and how to word a rule so a model acts on it.
subject_version: "Claude Code docs, Claude platform prompting docs and agents.md as of 2026-10-04; Codex, Cursor and Copilot docs as of 2026-10-04; arXiv 2507.11538, 2510.14842, 2511.12884, 2601.20404, 2602.11988, 2606.20512"
valid_for: "Claude Code 2.1.x and the Claude 4.6 to 5.x model line; vendor docs as of 2026-10"
generated:
  by: process:researching-references
  at: 2026-10-04T12:00:00+02:00
stale_after: 2027-04-04T00:00:00+00:00
status: draft
sources:
  - id: claude-code-best-practices
    title: Claude Code docs, Best practices for Claude Code
    resource: https://code.claude.com/docs/en/best-practices
    accessed: 2026-10-04
  - id: claude-code-memory
    title: Claude Code docs, How Claude remembers your project
    resource: https://code.claude.com/docs/en/memory
    accessed: 2026-10-04
  - id: claude-prompting
    title: Claude Developer Platform, Prompting best practices
    resource: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
    accessed: 2026-10-04
  - id: claude-sonnet-5
    title: Claude Developer Platform, Prompting Claude Sonnet 5
    resource: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5
    accessed: 2026-10-04
  - id: claude-opus-5
    title: Claude Developer Platform, Prompting Claude Opus 5
    resource: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
    accessed: 2026-10-04
  - id: claude-skills
    title: Claude Developer Platform, Skill authoring best practices
    resource: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
    accessed: 2026-10-04
  - id: anthropic-context
    title: Anthropic engineering, Effective context engineering for AI agents
    resource: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
    accessed: 2026-10-04
  - id: agents-md
    title: AGENTS.md, the open format for guiding coding agents
    resource: https://agents.md/
    accessed: 2026-10-04
  - id: aaif-measuring
    title: Agentic AI Foundation, Measuring AGENTS.md, what five runs show that one doesn't
    resource: https://aaif.io/blog/measuring-agents-md-what-five-runs-show-that-one-doesn-t
    accessed: 2026-10-04
  - id: codex-agents-md
    title: OpenAI Codex docs, AGENTS.md (redirect target of developers.openai.com/codex/guides/agents-md)
    resource: https://learn.chatgpt.com/docs/agent-configuration/agents-md
    accessed: 2026-10-04
  - id: cursor-rules
    title: Cursor docs, Rules
    resource: https://cursor.com/docs/context/rules
    accessed: 2026-10-04
  - id: copilot-instructions
    title: GitHub Docs, Adding repository custom instructions for GitHub Copilot
    resource: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
    accessed: 2026-10-04
  - id: ifscale
    title: Jaroslawicz et al., How Many Instructions Can LLMs Follow at Once? (arXiv 2507.11538, NeurIPS 2025)
    resource: https://arxiv.org/abs/2507.11538
    accessed: 2026-10-04
  - id: scaledif
    title: Elder, Duesterwald and Muthusamy, Boosting Instruction Following at Scale (arXiv 2510.14842)
    resource: https://arxiv.org/abs/2510.14842
    accessed: 2026-10-04
  - id: agent-readmes
    title: Chatlatanagulchai et al., Agent READMEs, An Empirical Study of Context Files for Agentic Coding (arXiv 2511.12884)
    resource: https://arxiv.org/abs/2511.12884
    accessed: 2026-10-04
  - id: lulla
    title: Lulla et al., On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents (arXiv 2601.20404)
    resource: https://arxiv.org/abs/2601.20404
    accessed: 2026-10-04
  - id: gloaguen
    title: Gloaguen et al., Evaluating AGENTS.md, Are Repository-Level Context Files Helpful for Coding Agents? (arXiv 2602.11988)
    resource: https://arxiv.org/html/2602.11988
    accessed: 2026-10-04
  - id: shepard
    title: Shepard and Albrecht, Probe-and-Refine Tuning of Repository Guidance for Coding Agents (arXiv 2606.20512)
    resource: https://arxiv.org/html/2606.20512
    accessed: 2026-10-04
  - id: humanlayer
    title: HumanLayer, Writing a good CLAUDE.md
    resource: https://www.humanlayer.dev/blog/writing-a-good-claude-md
    accessed: 2026-10-04
---

# Agent instruction files

This reference records what the vendors of coding agents, the steward of the
`AGENTS.md` format and the published empirical studies say about the file an
agent loads on every turn (`AGENTS.md`, `CLAUDE.md`, rules files) and the
files it loads on demand (skills). It covers three questions: what belongs in
each file, how length and instruction count affect whether a rule is
followed, and how a rule should be worded so a model acts on it. It
deliberately leaves out tool and parameter descriptions, which
[MCP model-facing text](mcp-model-facing-text.md) covers, and the mechanics
of how each product discovers the files beyond what bears on authoring.

## Scope

- Covers: load mechanics that constrain authoring; what to include and
  exclude; measured effects of context files on agent success and cost;
  length and instruction-count effects; wording (directive form, emphasis,
  hedges, rationale); the review and pruning practices the sources
  recommend.
- Does not cover: MCP tool, resource or prompt descriptions; system prompts
  built for an API product; the file-discovery rules of agents other than
  Claude Code, Codex, Cursor and Copilot.
- Depended on by: `AGENTS.md.jinja` and every `.agents/skills/*/SKILL.md`
  (the text these claims judge); `template-ci`'s always-loaded budget step
  and `tests/test_agent_instructions.py` (the ceilings); the maintainer
  guide's "Always-loaded budget" section in the template's `CLAUDE.md`.

## Claims

### How the file reaches the model

- Claude Code reads `CLAUDE.md` at the start of every session and delivers
  its content "as a user message after the system prompt, not as part of
  the system prompt itself"; it is "context, not enforced configuration",
  with "no guarantee of strict compliance, especially for vague or
  conflicting instructions". [source: claude-code-memory]
- By default Claude Code reads `AGENTS.md` only when no `CLAUDE.md`,
  `.claude/CLAUDE.md` or `CLAUDE.local.md` exists in the working directory
  or above it; a `CLAUDE.md` that imports `@AGENTS.md` loads the imported
  file once and never twice. [source: claude-code-memory]
- `@path` imports "help you organize a long file but don't reduce its
  context cost, because imported files also load at launch"; only
  path-scoped rules under `.claude/rules/` with a `paths` field load on
  demand, when Claude works with a matching file. [source: claude-code-memory]
- A skill costs nothing at startup beyond its name and description; Claude
  reads `SKILL.md` "only when the Skill becomes relevant", so task-shaped
  guidance belongs there rather than in the always-loaded file.
  [source: claude-skills] [source: claude-code-best-practices]
- `CLAUDE.md` instructions "are advisory"; a hook "is deterministic and
  guarantee[s] the action happens". An instruction that must run at a fixed
  point, such as before every commit, is written as a hook instead.
  [source: claude-code-best-practices] [source: claude-code-memory]
- `AGENTS.md` is "just standard Markdown" with no required fields; nested
  files apply with "the closest AGENTS.md to the edited file wins", and
  "explicit user chat prompts override everything". [source: agents-md]
- Codex concatenates the `AGENTS.md` chain from the repository root to the
  current directory, later files overriding earlier ones because they
  appear later in the prompt, and stops adding files at
  `project_doc_max_bytes`, 32 KiB by default. [source: codex-agents-md]
- Copilot's repository instructions "must be no longer than 2 pages" and
  "must not be task specific". [source: copilot-instructions]
- Cursor applies a rule in one of four ways: always, auto-attached by glob,
  agent-selected from its description, or on manual mention; it recommends
  keeping a rule under 500 lines and splitting large rules into composable
  ones. [source: cursor-rules]
- `AGENTS.md` is "guidance, not enforcement"; the controls that guarantee
  behaviour are CI and branch protection. [source: aaif-measuring]

### What belongs in the always-loaded file

- Claude Code's include list: commands Claude cannot guess, code-style rules
  that differ from defaults, testing instructions and test runners,
  repository etiquette, project-specific architectural decisions, developer
  environment quirks, and "common gotchas or non-obvious behaviors". Its
  exclude list: anything Claude can figure out by reading code, standard
  language conventions, detailed API documentation, information that
  changes frequently, "long explanations or tutorials", file-by-file
  descriptions, and self-evident practices. [source: claude-code-best-practices]
- The per-line test: "For each line, ask: *Would removing this cause Claude
  to make mistakes?* If not, cut it." [source: claude-code-best-practices]
- "CLAUDE.md is loaded every session, so only include things that apply
  broadly. For domain knowledge or workflows that are only relevant
  sometimes, use skills instead." [source: claude-code-best-practices]
- Gloaguen et al. find that "context files do not provide effective
  overviews": with repository overviews present in 95 to 100 percent of the
  LLM-generated files, agents found the relevant files no faster. They
  recommend a context file "only contain specific additional instructions
  beyond what is already available in the codebase", and name "specifying
  non-standard coding practices" as the use that holds up. [source: gloaguen]
- The same study finds explicit tool instructions are followed: with `uv`
  named in the file, agents used it 1.6 times per instance against 0.01
  without; repository-specific tools 2.5 times against 0.05. [source: gloaguen]
- Shepard and Albrecht's refinement loop, which measurably raised resolve
  rate (33.0 percent against 28.3 for static guidance and 25.5 for none on
  SWE-bench Verified, p < 0.001), added lines of three kinds: procedural
  guardrails (47 percent, "Document the failing test name before fixing"),
  structural pointers to specific files and modules (30 percent, "Trace
  through subclasses.py for inheritance"), and quality gates (23 percent,
  "Show actual test output, not fabricated summaries"). Generic advice was
  replaced by specific: "Run the smallest relevant test first" became
  "Always reference the specific test class/method (e.g.,
  django/core/tests/test_checks.py::CheckTestCase)". [source: shepard]
- The gain from refined guidance came from "help[ing] agents reach the
  correct file rather than improving the quality of the changes they
  make": coverage rose 14.5 points while per-patch precision stayed near
  59 percent. [source: shepard]
- "Concrete instructions beat aspirational ones. 'Follow best practices'
  gives an agent nothing to act on. 'Run npm run lint after any source
  change' and 'do not edit files in dist/' give it commands, paths, and
  boundaries." [source: aaif-measuring]
- The format's own suggested sections: project overview, build and test
  commands, code style, testing instructions, security considerations,
  commit and pull-request guidelines, and "anything you'd tell a new
  teammate". [source: agents-md]
- In 2,303 real context files from 1,925 repositories, the most common
  instruction types were test procedures (75.9 percent), implementation
  details (70.8) and architecture (68.1); security (14.8) and performance
  (14.5) were the least common. The files "evolve like configuration code
  through frequent, small additions". [source: agent-readmes]
- Anthropic's system-prompt guidance: aim for "the minimal set of
  information that fully outlines your expected behavior", where "minimal
  does not necessarily mean short; you still need to give the agent
  sufficient information". The "right altitude" sits between "brittle"
  hardcoded logic and "vague, high-level guidance that fails to give the
  LLM concrete signals". Organise the prompt into distinct sections under
  Markdown headers or XML tags. [source: anthropic-context]
- Cursor: "Start simple. Add rules only when you notice Agent making the
  same mistake repeatedly"; point to canonical examples instead of copying
  code; do not add "instructions for edge cases that rarely apply".
  [source: cursor-rules]

### Length, instruction count and adherence

- Claude Code's size guidance: "target under 200 lines per CLAUDE.md file.
  Longer files consume more context and reduce adherence." "Bloated
  CLAUDE.md files cause Claude to ignore your actual instructions!" "If
  Claude keeps doing something you don't want despite having a rule against
  it, the file is probably too long and the rule is getting lost."
  [source: claude-code-memory] [source: claude-code-best-practices]
- The named failure pattern: "The over-specified CLAUDE.md. If your
  CLAUDE.md is too long, Claude ignores half of it because important rules
  get lost in the noise. Fix: Ruthlessly prune. If Claude already does
  something correctly without the instruction, delete it or convert it to a
  hook." [source: claude-code-best-practices]
- A skill body should stay "under 500 lines for optimal performance", with
  further material split into files one level deep that Claude reads on
  demand; "Not every token in your Skill has an immediate cost", but once
  loaded "every token competes with conversation history and other
  context". [source: claude-skills]
- Instruction following degrades with instruction density. Across 20
  models on IFScale, "even the best frontier models only achieve 68%
  accuracy at the max density of 500 instructions", with a "bias towards
  earlier instructions" and three decay shapes: threshold decay for
  reasoning models, linear decay (gpt-4.1, claude-sonnet-4), exponential
  decay for smaller models. Errors split into omissions and modifications.
  [source: ifscale]
- "An important factor contributing to this trend is the degree of tension
  and conflict that arises as the number of instructions is increased";
  the authors ship a conflict-scoring tool for prompt instructions.
  [source: scaledif]
- Claude Code says the same of contradictions: "if two instructions
  contradict each other, Claude may pick one arbitrarily"; user rules and
  project rules do not override each other either. `/doctor prompt-audit`
  reports "instructions written for older models, references to files or
  commands that don't exist, and files that contradict each other" across
  `CLAUDE.md`, `AGENTS.md`, rules and skills, proposing edits it does not
  apply. [source: claude-code-memory]
- Gloaguen et al. find "no clear dependency between the success rate or the
  per-instance cost and the context file length". The cost comes from
  following what the file says: more grep and file reads, more test runs,
  and more thinking (GPT-5.2 spent 22 percent more reasoning tokens with a
  context file). LLM-generated files changed resolve rate by −0.5 points
  on SWE-bench and −2 on their own benchmark at about 20 percent more cost;
  developer-written files gave +2.4 points (p = 0.21) at up to 19 percent
  more cost. [source: gloaguen]
- Lulla et al., measuring 124 pull requests across 10 repositories, find a
  present `AGENTS.md` "associated with a lower median runtime (Δ 28.64%)
  and reduced output token consumption (Δ 16.58%), while maintaining a
  comparable task completion behavior"; the paper does not say which
  content produced the saving. [source: lulla]
- A twelve-line `AGENTS.md` cut wall time 27 percent and credits 24 percent
  on an ambiguous task over five runs per condition; single runs "produced
  misleading results". [source: aaif-measuring]
- Shepard and Albrecht cap refined guidance at 3,000 characters, trimming
  "boilerplate" and "the longest bullets" to stay within it; refined files
  averaged 2,754 characters against 1,687 for the static baseline, so the
  gain was not from brevity but from "identifying what that text should
  say". [source: shepard]
- Codex truncates at 32 KiB; the only hard byte limit among the four
  products. [source: codex-agents-md]
- Context has an "attention budget" that depletes per token; as the context
  grows "the model's ability to accurately recall information from that
  context decreases" (context rot). [source: anthropic-context]
- HumanLayer recommends under 300 lines, "and shorter is even better", keeps
  its own root file under sixty lines, and states that "frontier thinking
  LLMs can follow ~150-200 instructions with reasonable consistency" while
  Claude Code's own system prompt "contains ~50 individual instructions";
  past that, a model "begins to ignore all of them uniformly".
  [source: humanlayer] [unverified] The instruction-count figures cite no
  measurement; IFScale is the nearest published evidence and uses a
  different task.

### Wording a rule

- Write instructions "concrete enough to verify": "Use 2-space indentation"
  instead of "Format code properly"; "Run `npm test` before committing"
  instead of "Test your changes"; "API handlers live in `src/api/handlers/`"
  instead of "Keep files organized". [source: claude-code-memory]
- "Tell Claude what to do instead of what not to do": "Your response should
  be composed of smoothly flowing prose paragraphs" rather than "Do not use
  markdown in your response". [source: claude-prompting]
- Emphasis is a scarce resource: "If Claude keeps skipping one instruction,
  add emphasis such as 'IMPORTANT' to that line alone. If you emphasize
  many lines, none of them stands out." [source: claude-code-best-practices]
- Claude Opus 4.5 and later "are also more responsive to the system
  prompt"; prompts written to stop undertriggering "may now overtrigger",
  and the fix is to "dial back any aggressive language": "Use this tool
  when..." in place of "CRITICAL: You MUST use this tool when...".
  [source: claude-prompting]
- Claude Sonnet 5 "interprets prompts literally and explicitly"; it "does
  not silently generalize an instruction from one item to another, and it
  does not infer requests you didn't make". A rule meant to apply broadly
  must state its scope. [source: claude-sonnet-5]
- A softening instruction is followed as written: a review prompt saying
  "only report high-severity issues", "be conservative" or "don't nitpick"
  makes Sonnet 5 and Opus 5 investigate as thoroughly and report less, so
  the docs tell authors to "be concrete about where the bar is rather than
  using qualitative terms like 'important'". [source: claude-sonnet-5]
  [source: claude-opus-5]
- Explaining why helps: "Providing context or motivation behind your
  instructions, such as explaining to Claude why such behavior is
  important, can help Claude better understand your goals"; the worked
  example replaces "NEVER use ellipses" with "Your response will be read
  aloud by a text-to-speech engine, so never use ellipses since the
  text-to-speech engine will not know how to pronounce them", and "Claude
  is smart enough to generalize from the explanation". [source: claude-prompting]
- The same vendor excludes "long explanations or tutorials" from
  `CLAUDE.md` and tells skill authors to challenge each piece of
  information with "Does Claude really need this explanation?", "Can I
  assume Claude knows this?" and "Does this paragraph justify its token
  cost?", under the default assumption that "Claude is already very
  smart". Its verbose counter-example spends three sentences explaining
  what a PDF is and why a library is needed before the one line that
  matters. [source: claude-code-best-practices] [source: claude-skills]
- Reading those two together: the motivation that earns its place is the
  one the model needs to decide an unlisted case (the text-to-speech engine
  tells it what else to avoid), stated in the same sentence as the rule;
  the explanation that does not is the one that justifies the rule's
  existence to a human or narrates how it is enforced. No source measures
  this split directly. [unverified] A paired evaluation of a rule with and
  without its rationale clause would settle it.
- Match freedom to fragility: exact scripts and "Do not modify the command"
  where "operations are fragile and error-prone" or "a specific sequence
  must be followed"; heuristics and general direction where "multiple
  approaches are valid" and "decisions depend on context". [source: claude-skills]
- "Avoid offering too many options": give a default with one escape hatch
  rather than a list of alternatives. Use one term per concept throughout.
  Keep time-sensitive content out of the main text. [source: claude-skills]
- For a sequence, "provide instructions as sequential steps using numbered
  lists or bullet points when the order or completeness of steps matters";
  "organized sections are easier for Claude to follow than dense
  paragraphs". [source: claude-prompting] [source: claude-code-memory]
- Positive examples of the wanted output "tend to be more effective than
  negative examples or instructions that tell the model what not to do",
  for conciseness and for communication style alike. [source: claude-sonnet-5]
  [source: claude-opus-5]
- Claude Opus 5 "verifies its own work without being told to"; explicit
  verification instructions "cause over-verification" and are to be
  removed, as are "double-check your answer" re-check instructions.
  [source: claude-opus-5]
- Claude Opus 5's written deliverables, "files that Claude Opus 5 writes to
  disk (reports, Markdown documents, summaries)", run longer than earlier
  models' and need "explicit length calibration": "cover the substance, but
  do not pad with filler sections, redundant summaries, or boilerplate".
  [source: claude-opus-5] This is documented for output the model writes
  for a human; no source measures it for instruction files the model
  edits.

### Reviewing and pruning without losing rules

- "Treat CLAUDE.md like code: review it when things go wrong, prune it
  regularly, and test changes by observing whether Claude's behavior
  actually shifts." `/doctor` "proposes cuts for content it can derive from
  the codebase". [source: claude-code-best-practices]
- Skill authoring is evaluation-driven: run the task without the skill and
  record the failures, build three scenarios that test those gaps, measure
  a baseline, "write minimal instructions" that address the gaps, then
  iterate. When reviewing a drafted skill, "check that Claude A hasn't
  added unnecessary explanations", for example "Remove the explanation
  about what win rate means - Claude already knows that". Test with every
  model the skill will run on: for Opus the question is "Does the Skill
  avoid over-explaining?", for Haiku "Does the Skill provide enough
  guidance?". [source: claude-skills]
- Shepard and Albrecht's refine step is a deterministic procedure that
  "inserts, modifies, or strengthens guidance sections, filters boilerplate,
  and trims longest bullets to enforce budget", driven by probe failures
  rather than by reading; they advise to "tune guidance with the model that
  will consume it" and to make sure "the step budget accommodates the
  prescribed workflow". [source: shepard]
- A single run is not evidence that a change to the file helped or hurt;
  five runs per condition were needed to see a stable effect.
  [source: aaif-measuring]
- Claude Code's own review loop for a rule that is not followed: confirm the
  file loaded (`/context`), make the instruction more specific, look for a
  conflicting instruction in another loaded file, and check whether it
  competes with guidance Claude Code adds on its own.
  [source: claude-code-memory]

## Where this project departs from the subject

- The template budgets 24,000 characters of template-owned prose in a
  rendered `AGENTS.md` and 40,000 for the whole file (`CLAUDE.md`, "Always-
  loaded budget"). The smoke render at the template's `df67fcd` (v11.1.3)
  is 252 lines and 23,522 characters, above Claude Code's 200-line target
  and below Codex's 32 KiB cut. [observed: `wc -l -c AGENTS.md` on a
  `copier copy --defaults --data-file tests/fixtures/smoke-answers.yml`
  render] The budget is a ceiling, not a target; issue #768 records that
  the render sits at 98 percent of it.
- The template's `AGENTS.md.jinja` carries rationale and enforcement
  narrative alongside its rules (issue #768). The sources above treat
  rationale as a one-clause scope aid and narrative as excluded content;
  the project has not yet decided where its rationale goes.

## Not covered

- No source measures hedged wording ("prefer", "consider", "where
  possible") directly. The literal-following notes for Sonnet 5 and Opus 5
  are the nearest evidence that a hedge is read as written rather than as
  a strong default. A paired evaluation of hedged against conditional
  wording would settle it.
- No source derives a character budget for Claude Code from a client limit;
  the 200-line figure is a target, and only Codex (32 KiB) and Copilot (two
  pages) state a cut.
- No study isolates the adherence cost of rationale sentences; Gloaguen et
  al. measured repository overviews, Shepard and Albrecht measured whole
  files.
- Whether the always-loaded file reaches the hosted `@claude` review
  workflow in the same form as an interactive session is a property of
  that workflow's harness, not of these sources.
