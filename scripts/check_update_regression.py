"""Regression check for the copier-update generation ordering.

The bug class this guards (issue #291 item 4): on ``copier update``,
``_tasks`` run after template-owned files are re-rendered but before the
old-render → project diff restores domain content, so a generation task
running then scans the domain-less skeleton ``config.py`` and rewrites the
skip-listed (never-patched) artifacts with every domain var stripped —
silently, because scanning a config that genuinely has no domain fields
fails nothing. The fix gates the task to ``copier copy`` and regenerates
via an after-stage ``_migrations`` entry instead; this script proves that
end-to-end with a real ``copier update``:

1. Render the template at ``BASE_REF`` (a released tag) into a scratch
   project.
2. Inject one domain field + literal ``env()`` read into the config
   sentinels, regenerate, and assert the var landed in ``.env.example``.
3. Commit, then ``copier update --trust`` to the working tree's ``HEAD``.
4. Assert the var survived in the generated artifacts and that
   ``gen_config_surface.py --check`` exits clean — the exact state the
   pre-fix ordering could not produce without a manual re-run.

Runs copier via ``uv run --no-project --with copier`` (matching how
template-ci and the local workflow invoke it), so ``uv`` must be on PATH.
The template repo must have its release tags fetched: copier checks
``BASE_REF`` out of a fresh clone of the repo, and describes ``HEAD``
against tags to order the update.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

# First release whose update path carries the generated config artifacts
# with the #282 skip-listing mechanics — the oldest ancestry the ordering
# fix must survive from.
BASE_REF = "v3.0.2"

_FIELD = (
    "    vault_path: str = field(\n"
    '        default="/data/vault",\n'
    '        metadata={"help": "Filesystem root of the vault.",'
    ' "tags": ("storage",)},\n'
    "    )\n"
)
_READ = '            vault_path=env(_ENV_PREFIX, "VAULT_PATH", "/data/vault"),\n'
_VAR = "SMOKE_MCP_VAULT_PATH"


def _run(args: list[str], cwd: Path) -> None:
    result = subprocess.run(args, cwd=cwd, check=False)
    if result.returncode != 0:
        raise SystemExit(f"ERROR: {' '.join(args)} exited {result.returncode}")


def _copier(args: list[str], cwd: Path) -> None:
    _run(["uv", "run", "--no-project", "--with", "copier", "copier", *args], cwd)


def _git(args: list[str], cwd: Path) -> None:
    _run(
        [
            "git",
            "-c",
            "user.email=template-ci@localhost",
            "-c",
            "user.name=template-ci",
            *args,
        ],
        cwd,
    )


def _inject_domain_var(project: Path) -> None:
    config = project / "src" / "smoke_mcp" / "config.py"
    text = config.read_text(encoding="utf-8")
    for marker, insert in (
        ("    # CONFIG-FIELDS-END", _FIELD),
        ("            # CONFIG-FROM-ENV-END", _READ),
    ):
        if marker not in text:
            raise SystemExit(f"ERROR: {config} is missing sentinel {marker!r}")
        text = text.replace(marker, insert + marker)
    config.write_text(text, encoding="utf-8")


def _assert_var(project: Path, rel_path: str, *, expected: bool) -> None:
    text = (project / rel_path).read_text(encoding="utf-8")
    if (_VAR in text) is not expected:
        state = "missing from" if expected else "unexpectedly present in"
        raise SystemExit(f"ERROR: {_VAR} {state} {rel_path} — update regression")


def _assert_review_workflow_default(project: Path) -> None:
    workflows = project / ".github" / "workflows"
    if (workflows / "claude-code-review.yml").exists():
        raise SystemExit(
            "ERROR: copier update retained automatic Claude review despite "
            "enable_automatic_claude_review defaulting to false"
        )
    if not (workflows / "claude.yml").is_file():
        raise SystemExit("ERROR: copier update removed the explicit @claude responder")


def main() -> int:
    template_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="update-regression-") as tmp:
        project = Path(tmp) / "proj"

        _copier(
            [
                "copy",
                "--trust",
                "--defaults",
                f"--vcs-ref={BASE_REF}",
                "--data-file",
                str(template_root / "tests" / "fixtures" / "smoke-answers.yml"),
                str(template_root),
                str(project),
            ],
            template_root,
        )

        # `copier copy .` records `_src_path: .`, which `copier update`
        # would resolve relative to the project. Point it back at the
        # template checkout.
        answers = project / ".copier-answers.yml"
        answers.write_text(
            answers.read_text(encoding="utf-8").replace(
                "_src_path: .", f"_src_path: {template_root}"
            ),
            encoding="utf-8",
        )

        _inject_domain_var(project)
        _run([sys.executable, "scripts/gen_config_surface.py"], project)
        _assert_var(project, ".env.example", expected=True)

        _git(["init", "-q"], project)
        _git(["add", "-A"], project)
        _git(["commit", "-q", "-m", f"scaffold at {BASE_REF} + domain var"], project)

        _copier(["update", "--trust", "--defaults", "--vcs-ref=HEAD"], project)
        _assert_review_workflow_default(project)

        _assert_var(project, ".env.example", expected=True)
        _assert_var(
            project,
            "docs/javascripts/config-wizard/wizard-spec.json",
            expected=True,
        )
        _run([sys.executable, "scripts/gen_config_surface.py", "--check"], project)

    print(f"update regression OK: {_VAR} survived {BASE_REF} -> HEAD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
