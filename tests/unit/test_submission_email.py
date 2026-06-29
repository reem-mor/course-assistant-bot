"""Byte-for-byte tests of the submission email format (Section 4.3)."""

from __future__ import annotations

from app.domain.models import DraftAttachment, SubmissionDraft
from app.services.submission import build_body, build_subject


def test_subject_exact_format() -> None:
    subject = build_subject(
        full_name="John Doe", topic="Python Basics", date_ddmmyyyy="12/05/2026"
    )
    assert subject == (
        "[Oz VeRuach] Homework Submission \u2013 John Doe \u2013 Python Basics \u2013 12/05/2026"
    )


def _full_draft() -> SubmissionDraft:
    return SubmissionDraft(
        full_name="John Doe",
        topic="Python Basics",
        date_ddmmyyyy="12/05/2026",
        work="Implemented a CLI todo app.",
        tech="Python, argparse.",
        challenges="Argparse subcommands were tricky; solved via subparsers.",
        attachments=[
            DraftAttachment(filename="todo.py", content=b"x", mime_type="text/x-python")
        ],
        github_link="https://github.com/x/y",
    )


def test_body_byte_for_byte_with_challenges() -> None:
    expected = (
        "Hi Alex,\n"
        "\n"
        "This is my submission for the Python Basics assignment.\n"
        "\n"
        "What I implemented:\n"
        "Implemented a CLI todo app.\n"
        "\n"
        "Key concepts and technologies:\n"
        "Python, argparse.\n"
        "\n"
        "Challenges and how I addressed them:\n"
        "Argparse subcommands were tricky; solved via subparsers.\n"
        "\n"
        "Please find attached:\n"
        "- todo.py\n"
        "- GitHub: https://github.com/x/y\n"
        "\n"
        "I would appreciate your feedback on this submission.\n"
        "\n"
        "Best regards,\n"
        "John Doe"
    )
    assert build_body(_full_draft()) == expected


def test_body_omits_challenges_when_absent() -> None:
    draft = _full_draft()
    draft.challenges = None
    body = build_body(draft)
    assert "Challenges and how I addressed them:" not in body


def test_body_no_attachments_placeholder() -> None:
    draft = _full_draft()
    draft.attachments = []
    draft.github_link = None
    body = build_body(draft)
    assert "- (none provided)" in body
