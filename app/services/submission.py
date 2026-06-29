"""Homework submission email composition + the C8 guardrail.

The email is composed deterministically so the subject matches Section 4.3 byte-for-byte
and the body follows the prescribed structure exactly. The email_writer model may polish
prose later, but this deterministic form is canonical and always available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.i18n import Language
from app.core.settings import Settings
from app.domain.models import DraftState, SubmissionDraft
from app.services.email import EmailAttachment, EmailService

# En dash (U+2013) with surrounding spaces, exactly as in the 4.3 subject example.
_SUBJECT_TEMPLATE = "[Oz VeRuach] Homework Submission \u2013 {name} \u2013 {topic} \u2013 {date}"


@dataclass(frozen=True)
class SubmissionEmail:
    """A fully composed submission email ready to hand to an EmailService."""

    to: str
    cc: str | None
    subject: str
    body: str
    attachments: list[EmailAttachment]


def build_subject(*, full_name: str, topic: str, date_ddmmyyyy: str) -> str:
    """Build the exact 4.3 subject line."""
    return _SUBJECT_TEMPLATE.format(name=full_name, topic=topic, date=date_ddmmyyyy)


def _attachment_lines(draft: SubmissionDraft) -> str:
    lines = [f"- {att.filename}" for att in draft.attachments]
    if draft.github_link:
        lines.append(f"- GitHub: {draft.github_link}")
    if not lines:
        lines.append("- (none provided)")
    return "\n".join(lines)


def build_body(draft: SubmissionDraft) -> str:
    """Build the deterministic, professional-English body per 4.3 structure."""
    sections = [
        "Hi Alex,",
        "",
        f"This is my submission for the {draft.topic} assignment.",
        "",
        "What I implemented:",
        draft.work or "",
        "",
        "Key concepts and technologies:",
        draft.tech or "",
    ]
    if draft.challenges:
        sections += ["", "Challenges and how I addressed them:", draft.challenges]
    sections += [
        "",
        "Please find attached:",
        _attachment_lines(draft),
        "",
        "I would appreciate your feedback on this submission.",
        "",
        "Best regards,",
        draft.full_name or "",
    ]
    return "\n".join(sections)


def compose_email(draft: SubmissionDraft, settings: Settings) -> SubmissionEmail:
    """Compose the submission email, sourcing recipients from settings (never hardcoded)."""
    attachments = [
        EmailAttachment(filename=a.filename, content=a.content, mime_type=a.mime_type)
        for a in draft.attachments
    ]
    return SubmissionEmail(
        to=settings.hw_to_email or "",
        cc=settings.hw_cc_email,
        subject=build_subject(
            full_name=draft.full_name or "",
            topic=draft.topic or "",
            date_ddmmyyyy=draft.date_ddmmyyyy or "",
        ),
        body=build_body(draft),
        attachments=attachments,
    )


async def finalize_and_send(
    draft: SubmissionDraft, service: EmailService, settings: Settings
) -> str:
    """Send a confirmed draft and return the provider message id.

    Guards against double-send; on send failure the exception propagates and the draft
    stays ``confirmed`` so the caller can offer a retry.
    """
    if draft.state is DraftState.SENT:
        raise ValueError("draft already sent")
    if draft.state is not DraftState.CONFIRMED:
        raise ValueError(f"draft must be confirmed before sending (state={draft.state})")
    email = compose_email(draft, settings)
    message_id = await service.send(
        to=email.to,
        cc=email.cc,
        subject=email.subject,
        body=email.body,
        attachments=email.attachments,
    )
    draft.mark_sent()
    return message_id


# --- C8 academic-integrity guardrail -----------------------------------------
_SOLVE_RE = re.compile(
    r"do (?:my|the) homework|solve (?:my|the|this) (?:homework|assignment|exercise)|"
    r"write the (?:homework|solution|code) for me|"
    r"עשה[^\n]{0,20}(?:שיעורי\s*בית|מטלה)|תפתור|פתור[^\n]{0,20}(?:מטלה|תרגיל)",
    re.IGNORECASE,
)


def looks_like_solve_request(text: str) -> bool:
    """True if the user is asking the bot to *do* the homework (not draft the email)."""
    return bool(_SOLVE_RE.search(text))


def scaffold_disclaimer(language: Language) -> str:
    """Return the labeled starter-scaffold disclaimer (C8)."""
    if language == "he":
        return (
            "זהו קורס לימודי — לא אכתוב עבורכם פתרון מלא להגשה. "
            "אני יכול לספק *שלד התחלתי + רמזים* שתשלימו בעצמכם, "
            "או לעזור לנסח את מייל ההגשה. מה תעדיפו?"
        )
    return (
        "This is a learning course — I won't write a complete graded solution for you. "
        "I can provide a *starter scaffold + hints* for you to complete yourself, "
        "or help draft your submission email. Which would you like?"
    )
