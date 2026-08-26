"""Guard the downstream Renovate shape that keeps rebase storms and
missed windows away (#506).

Two facts from the Renovate docs drive it: `rebaseWhen: auto` becomes
`behind-base-branch` once automerge is on, so every merge rebases every
open branch — grouping non-major updates into one PR is the documented
lever; and `schedule` windows have hour granularity in UTC, so the runner
cron must land inside `lockFileMaintenance`'s window or it never fires.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DOWNSTREAM_CONFIG = REPO / "renovate.json.jinja"
DOWNSTREAM_RUNNER = REPO / ".github" / "workflows" / "renovate.yml.jinja"
TEMPLATE_RUNNER = REPO / ".github" / "workflows" / "template-renovate.yml"
DAYS = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")


def _config() -> dict:
    # No Jinja inside the file: its bytes are the render.
    text = DOWNSTREAM_CONFIG.read_text(encoding="utf-8")
    assert "{{" not in text and "{%" not in text
    return json.loads(text)


def _cron(path: Path) -> str:
    # `{% raw %}` blocks make the workflow jinja YAML-parseable as-is.
    text = (
        path.read_text(encoding="utf-8")
        .replace("{% raw %}", "")
        .replace("{% endraw %}", "")
    )
    parsed = yaml.safe_load(text)
    (entry,) = parsed[True if True in parsed else "on"]["schedule"]
    return entry["cron"]


def _cron_fires(cron: str) -> set[tuple[int, int]]:
    """(weekday 0=Sunday, hour) pairs a `M H * * D` cron fires on, for the
    cron shapes this repo uses: numeric minute, `*` or `*/N` hours, `*` or a
    numeric day-of-week list."""
    minute, hour, dom, month, dow = cron.split()
    assert dom == "*" and month == "*", cron
    assert minute.isdigit() and int(minute) != 0, (
        f"{cron!r}: use a non-zero minute; GitHub delays top-of-hour schedules"
    )
    if hour == "*":
        hours = range(24)
    else:
        m = re.fullmatch(r"\*/(\d+)", hour)
        assert m, f"unsupported hour field in {cron!r}"
        hours = range(0, 24, int(m.group(1)))
    days = range(7) if dow == "*" else [int(d) for d in dow.split(",")]
    return {(d, h) for d in days for h in hours}


def _window(schedule: str) -> set[tuple[int, int]]:
    """Renovate 'before Nam on <day>' → (weekday, hour) pairs, hour granularity."""
    m = re.fullmatch(r"before (\d+)am on (\w+)", schedule)
    assert m, f"unsupported schedule shape {schedule!r}"
    return {(DAYS.index(m.group(2)), h) for h in range(int(m.group(1)))}


def test_non_major_updates_are_grouped() -> None:
    assert "group:allNonMajor" in _config()["extends"]


def test_no_concurrency_cap_can_starve_the_lockfile_branch() -> None:
    # Human-gated majors stay open for weeks; a branch/PR cap would count them
    # and silently skip the weekly lock-file branch (review finding on #506).
    cfg = _config()
    assert "branchConcurrentLimit" not in cfg and "prConcurrentLimit" not in cfg


def test_no_release_age_gate() -> None:
    # A uniform delay would hold back security fixes too (owner decision, #506).
    cfg = _config()
    assert "minimumReleaseAge" not in cfg
    assert all("minimumReleaseAge" not in rule for rule in cfg["packageRules"])


def test_downstream_cron_hits_the_declared_lockfile_window() -> None:
    lfm = _config()["lockFileMaintenance"]
    assert lfm["enabled"] is True
    (schedule,) = lfm["schedule"]
    hit = _cron_fires(_cron(DOWNSTREAM_RUNNER)) & _window(schedule)
    assert hit, f"cron {_cron(DOWNSTREAM_RUNNER)!r} never runs inside {schedule!r}"


def test_runners_are_at_most_four_hourly() -> None:
    # Renovate's docs ask for windows of 3-4h unless the runner is more frequent.
    for runner in (DOWNSTREAM_RUNNER, TEMPLATE_RUNNER):
        fires = _cron_fires(_cron(runner))
        assert len({h for _, h in fires}) >= 6, (
            f"{runner.name}: fewer than 6 runs a day"
        )
