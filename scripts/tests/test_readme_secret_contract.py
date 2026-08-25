from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_claude_token_setup_is_explicitly_optional() -> None:
    text = (REPO / "README.md.jinja").read_text(encoding="utf-8")
    secrets = text[text.index("## GitHub secrets") : text.index("## Local development")]

    assert "two required repository secrets" in secrets
    assert "Optional" in secrets
    assert "`@claude`" in secrets
    assert "opted-in automatic review" in secrets
    assert "# Optional" in secrets
