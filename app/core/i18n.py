"""Minimal i18n scaffolding (he/en).

Phase 0 only needs onboarding and echo strings; later phases extend the catalog.
User-facing strings live here, never inline in handlers. Hebrew is the default when
language detection is ambiguous, matching the cohort.
"""

from __future__ import annotations

from typing import Literal

Language = Literal["he", "en"]

DEFAULT_LANGUAGE: Language = "he"

# A heuristic good enough for Phase 0: any Hebrew code-point => Hebrew.
_HEBREW_RANGE = range(0x0590, 0x05FF + 1)

_CATALOG: dict[str, dict[Language, str]] = {
    "start": {
        "he": (
            "שלום! אני העוזר הרשמי של קורס \"עוז ורוח\". 🤖\n\n"
            "בקרוב אוכל לעזור עם: לוח הזמנים והשיעור הבא, סיכומי שיעורים, "
            "חומרי לימוד מומלצים, שיעורי בית והגשתם, והקלטות.\n\n"
            "כרגע אני בהרצה ראשונית (שלב 0) — שלחו הודעה ואחזיר אותה כהד."
        ),
        "en": (
            "Hi! I'm the official assistant for the \"Oz VeRuach\" course. 🤖\n\n"
            "Soon I'll help with: schedule and next lesson, lesson summaries, "
            "recommended materials, homework and submissions, and recordings.\n\n"
            "Right now I'm in early bring-up (Phase 0) — send a message and I'll echo it."
        ),
    },
    "echo_prefix": {
        "he": "קיבלתי",
        "en": "You said",
    },
    "empty_message": {
        "he": "לא קיבלתי טקסט לטיפול.",
        "en": "I didn't receive any text to handle.",
    },
    "rate_limited": {
        "he": "רק רגע — בקשה כבדה כבר בעיבוד. נסו שוב עוד מספר שניות.",
        "en": "Easy there — a heavy request is already running. Try again in a few seconds.",
    },
    "myid": {
        "he": "מזהה ה-Telegram המספרי שלך הוא: {id}\nתפקיד: {role}",
        "en": "Your numeric Telegram ID is: {id}\nRole: {role}",
    },
    "role_owner": {"he": "בעלים (מנהל-על)", "en": "owner (superadmin)"},
    "role_admin": {"he": "מנהל", "en": "admin"},
    "role_student": {"he": "סטודנט", "en": "student"},
    # --- Schedule (Phase 1) ---------------------------------------------------
    "sched_next_header": {"he": "השיעור הבא:", "en": "Next lesson:"},
    "sched_week_header": {
        "he": "השבוע ({start}–{end}):",
        "en": "This week ({start}–{end}):",
    },
    "sched_week_empty": {
        "he": "אין שיעורים מתוכננים השבוע.",
        "en": "No sessions are scheduled this week.",
    },
    "sched_full_header": {"he": "מערכת השעות המלאה:", "en": "Full course schedule:"},
    "sched_week_group": {"he": "שבוע {n}", "en": "Week {n}"},
    "sched_course_finished": {
        "he": "הקורס הסתיים — כל השיעורים כבר התקיימו.",
        "en": "The course has finished — all sessions are in the past.",
    },
    "sched_holiday_today": {
        "he": "לתשומת לבכם: היום חג/חופשה, אין שיעור רגיל.",
        "en": "Heads up: today is a holiday/break, no regular class.",
    },
    "sched_nontechnical_note": {
        "he": "הערה: מפגש שאינו טכני — לרוב אין חומרי קורס/הקלטה.",
        "en": "Note: non-technical session — usually no course materials/recording.",
    },
    "label_instructor": {"he": "מרצה", "en": "Instructor"},
    "label_type": {"he": "סוג", "en": "Type"},
    "type_technical": {"he": "טכני", "en": "technical"},
    "type_workshop": {"he": "סדנה", "en": "workshop"},
    "type_milestone": {"he": "אבן דרך", "en": "milestone"},
    "type_holiday": {"he": "חג/חופשה", "en": "holiday"},
    "day_Sun": {"he": "יום ראשון", "en": "Sunday"},
    "day_Mon": {"he": "יום שני", "en": "Monday"},
    "day_Tue": {"he": "יום שלישי", "en": "Tuesday"},
    "day_Wed": {"he": "יום רביעי", "en": "Wednesday"},
    "day_Thu": {"he": "יום חמישי", "en": "Thursday"},
    "day_Fri": {"he": "יום שישי", "en": "Friday"},
    "day_Sat": {"he": "יום שבת", "en": "Saturday"},
    # --- Drive / recordings / homework (Phase 2) ------------------------------
    "drive_not_configured": {
        "he": "הגישה ל-Drive עדיין לא הוגדרה. פנו למפעיל הבוט.",
        "en": "Drive access isn't configured yet. Contact the bot operator.",
    },
    "rec_header": {"he": "הקלטה — {label}:", "en": "Recording — {label}:"},
    "rec_part_line": {"he": "חלק {n}: {url}", "en": "Part {n}: {url}"},
    "rec_not_linked": {
        "he": "ההקלטה של שיעור זה עדיין לא קושרה.",
        "en": "The recording for this lesson isn't linked yet.",
    },
    "rec_not_uploaded": {
        "he": "ההקלטה עדיין לא הועלתה.",
        "en": "The recording hasn't been uploaded yet.",
    },
    "rec_gap_note": {
        "he": "הערה: ייתכן שחלק מהחלקים חסרים.",
        "en": "Note: some parts may be missing.",
    },
    "rec_last_none": {
        "he": "לא נמצאה הקלטה אחרונה מקושרת עדיין.",
        "en": "No linked recent recording was found yet.",
    },
    "rec_all_header": {"he": "הקלטות זמינות:", "en": "Available recordings:"},
    "rec_all_item_empty": {"he": "{label}: טרם הועלתה", "en": "{label}: not uploaded yet"},
    "rec_all_item_count": {
        "he": "{label}: {n} חלקים",
        "en": "{label}: {n} part(s)",
    },
    "hw_header": {"he": "המטלה האחרונה ({lesson}):", "en": "Latest homework ({lesson}):"},
    "hw_item": {"he": "• {title}: {url}", "en": "• {title}: {url}"},
    "hw_multiple_note": {
        "he": "נמצאו כמה מטלות — בחרו אחת:",
        "en": "Multiple homework docs found — pick one:",
    },
    "hw_none": {
        "he": "לא נמצאה מטלה זמינה עדיין.",
        "en": "No homework was found yet.",
    },
    # --- Admin / lesson_map (Phase 2) -----------------------------------------
    "admin_refused": {
        "he": "הפקודה הזו מיועדת למנהלים בלבד.",
        "en": "This command is for admins only.",
    },
    "owner_refused": {
        "he": "הפקודה הזו מיועדת לבעלים בלבד.",
        "en": "This command is for the owner only.",
    },
    "map_header": {"he": "מיפוי השיעורים (lesson_map):", "en": "Lesson map:"},
    "map_recordings_label": {
        "he": "תיקיות הקלטה של אלכס:",
        "en": "Alex's recording folders:",
    },
    "map_links_label": {"he": "קישורים מאומתים:", "en": "Confirmed session links:"},
    "map_no_links": {"he": "אין עדיין קישורים מאומתים.", "en": "No confirmed links yet."},
    "map_suggest_header": {
        "he": "הצעות מיפוי (לא הוחלו — אשרו עם /map link):",
        "en": "Mapping suggestions (not applied — confirm with /map link):",
    },
    "map_suggest_none": {"he": "אין הצעות חדשות.", "en": "No new suggestions."},
    "map_link_saved": {
        "he": "נשמר: {date} → הקלטה {rec}, מצגת {pres}",
        "en": "Saved: {date} -> recording {rec}, presentation {pres}",
    },
    "map_usage": {
        "he": (
            "שימוש:\n/map — הצגת המיפוי\n/map suggest — הצעות\n"
            "/map link <YYYY-MM-DD> rec=<מספר> pres=<מספר>"
        ),
        "en": (
            "Usage:\n/map — show the map\n/map suggest — proposals\n"
            "/map link <YYYY-MM-DD> rec=<n> pres=<n>"
        ),
    },
    # --- Summaries (Phase 3) --------------------------------------------------
    "sum_header": {"he": "סיכום — {lesson}:", "en": "Summary — {lesson}:"},
    "sum_no_materials": {
        "he": "אין עדיין חומרים מקושרים לשיעור הזה לסיכום.",
        "en": "No materials are linked yet for this lesson to summarize.",
    },
    "sum_llm_unavailable": {
        "he": "שירות הסיכום אינו זמין כרגע (לא הוגדר ספק מודל).",
        "en": "Summaries aren't available right now (no model provider configured).",
    },
    "sum_working": {
        "he": "עובד על סיכום מההקלטה — זה עשוי לקחת רגע…",
        "en": "Working on a summary from the recording — this may take a moment…",
    },
    # --- Homework submission flow (Phase 4) -----------------------------------
    "sub_ask_name": {
        "he": "בואו נכין את מייל ההגשה. מה השם המלא שלכם?",
        "en": "Let's prepare your submission email. What's your full name?",
    },
    "sub_ask_topic": {
        "he": "מה הנושא/המטלה? (לדוגמה: Python Basics)",
        "en": "What's the topic/assignment? (e.g. Python Basics)",
    },
    "sub_ask_date": {
        "he": "תאריך ההגשה? שלחו DD/MM/YYYY או 'היום'.",
        "en": "Submission date? Send DD/MM/YYYY or 'today'.",
    },
    "sub_ask_work": {
        "he": "תארו בקצרה מה מימשתם.",
        "en": "Briefly describe what you implemented.",
    },
    "sub_ask_tech": {
        "he": "אילו מושגים/טכנולוגיות מרכזיים השתמשתם בהם?",
        "en": "Which key concepts/technologies did you use?",
    },
    "sub_ask_challenges": {
        "he": "אתגרים שנתקלתם בהם וכיצד פתרתם? (שלחו '-' לדילוג)",
        "en": "Any challenges and how you addressed them? (send '-' to skip)",
    },
    "sub_ask_attachments": {
        "he": "צרפו קבצים (קוד/מסמכים) ו/או שלחו קישור GitHub. סיימתם? שלחו /done.",
        "en": "Attach files (code/docs) and/or send a GitHub link. Done? send /done.",
    },
    "sub_attachment_added": {"he": "צורף: {name}", "en": "Attached: {name}"},
    "sub_attachment_too_large": {
        "he": "הקובץ גדול מדי לאימייל — צרפו קישור Drive/GitHub במקום.",
        "en": "That file is too large for email — share a Drive/GitHub link instead.",
    },
    "sub_no_attachments_warn": {
        "he": "אין קבצים מצורפים ואין קישור GitHub. לשלוח בכל זאת? לחצו שלח שוב לאישור.",
        "en": "No attachments and no GitHub link. Send anyway? Press Send again to confirm.",
    },
    "sub_preview_header": {"he": "תצוגה מקדימה של ההגשה:", "en": "Submission preview:"},
    "sub_label_to": {"he": "אל", "en": "To"},
    "sub_label_cc": {"he": "עותק", "en": "Cc"},
    "sub_label_subject": {"he": "נושא", "en": "Subject"},
    "sub_label_attachments": {"he": "צרופות", "en": "Attachments"},
    "sub_btn_send": {"he": "שלח ✅", "en": "Send ✅"},
    "sub_btn_edit": {"he": "עריכה ✏️", "en": "Edit ✏️"},
    "sub_btn_cancel": {"he": "ביטול ❌", "en": "Cancel ❌"},
    "sub_sent": {
        "he": "המייל נשלח בהצלחה. מזהה הודעה: {message_id}",
        "en": "Your submission email was sent. Message id: {message_id}",
    },
    "sub_send_failed": {
        "he": "שליחת המייל נכשלה: {error}. הטיוטה נשמרה — נסו שוב.",
        "en": "Sending failed: {error}. Your draft is kept — try again.",
    },
    "sub_cancelled": {"he": "ההגשה בוטלה.", "en": "Submission cancelled."},
    "sub_email_not_configured": {
        "he": "שליחת אימייל אינה מוגדרת כרגע. פנו למפעיל הבוט.",
        "en": "Email sending isn't configured yet. Contact the bot operator.",
    },
    "sub_edit_restart": {
        "he": "בואו נעבור שוב על הפרטים.",
        "en": "Let's go through the details again.",
    },
    "sub_hint_use_command": {
        "he": "כדי להכין הגשה שלחו /submit ואלווה אתכם בתהליך.",
        "en": "To prepare a submission, send /submit and I'll guide you through it.",
    },
    # --- Notifications + subscriptions + admin upload (Phase 5) ----------------
    "notify_new_material": {
        "he": "התווסף חומר חדש ({kind}){lesson}: {name}\n{link}",
        "en": "New material added ({kind}){lesson}: {name}\n{link}",
    },
    "notify_lesson_suffix": {"he": " לשיעור {lesson}", "en": " for {lesson}"},
    "kind_recording": {"he": "הקלטה", "en": "recording"},
    "kind_slides": {"he": "מצגת", "en": "slides"},
    "kind_homework": {"he": "מטלה", "en": "homework"},
    "kind_code": {"he": "קוד", "en": "code"},
    "kind_other": {"he": "קובץ", "en": "file"},
    "subscribed": {
        "he": "נרשמתם לעדכונים. שלחו /stop כדי לבטל, /menu לתפריט.",
        "en": "You're subscribed to updates. Send /stop to opt out, /menu for the menu.",
    },
    "unsubscribed": {
        "he": "ביטלתם את ההרשמה לעדכונים. עדיין תוכלו להשתמש בבוט לפי דרישה.",
        "en": "You've unsubscribed from broadcasts. You can still use the bot on demand.",
    },
    "menu_header": {"he": "מה תרצו לעשות?", "en": "What would you like to do?"},
    "menu_schedule": {"he": "לוח זמנים", "en": "Schedule"},
    "menu_recording": {"he": "הקלטות", "en": "Recordings"},
    "menu_homework": {"he": "שיעורי בית", "en": "Homework"},
    "menu_summary": {"he": "סיכום שיעור", "en": "Lesson summary"},
    "menu_submit": {"he": "הגשת מטלה", "en": "Submit homework"},
    "upload_ack": {
        "he": "קיבלתי את הקובץ. משדר לכל הנרשמים…",
        "en": "Got your file. Broadcasting to subscribers…",
    },
    "upload_broadcasted": {
        "he": "השידור הושלם: {sent} נשלחו, {failed} נכשלו.",
        "en": "Broadcast complete: {sent} sent, {failed} failed.",
    },
    "upload_drive_filed": {
        "he": "הקובץ גם תויק ב-Drive (מזהה: {file_id}).",
        "en": "The file was also filed to Drive (id: {file_id}).",
    },
    "upload_drive_disabled": {
        "he": "כתיבה ל-Drive מושבתת — בוצע שידור בלבד.",
        "en": "Drive write is disabled — broadcast only.",
    },
    # --- Recommendations + RAG (Phase 6) --------------------------------------
    "reindex_started": {
        "he": "מאנדקס מחדש את חומרי הקורס…",
        "en": "Reindexing course materials…",
    },
    "reindex_done": {
        "he": "האינדוקס הושלם: {count} קטעים.",
        "en": "Reindex complete: {count} chunks.",
    },
    "reindex_unavailable": {
        "he": "אינדוקס אינו זמין (חסר Drive או מפתח OpenAI להטמעות).",
        "en": "Indexing isn't available (Drive or the OpenAI embeddings key is missing).",
    },
    "rec_header_course": {"he": "מהקורס שלנו:", "en": "From our course:"},
    "rec_header_external": {"he": "קריאה מומלצת:", "en": "Recommended reading:"},
    "rec_none": {
        "he": "לא מצאתי חומרים מומלצים לנושא הזה עדיין.",
        "en": "I couldn't find recommended materials for that topic yet.",
    },
    "rec_ask_topic": {
        "he": "על איזה נושא להמליץ? לדוגמה: RAG, Docker, LangChain.",
        "en": "Which topic should I recommend for? e.g. RAG, Docker, LangChain.",
    },
    # --- Admin commands (Phase 7) ---------------------------------------------
    "admin_added": {"he": "נוסף מנהל: {id}", "en": "Admin added: {id}"},
    "admin_removed": {"he": "הוסר מנהל: {id}", "en": "Admin removed: {id}"},
    "admin_list": {"he": "מנהלים (DB): {ids}", "en": "Admins (DB): {ids}"},
    "admin_usage": {
        "he": "שימוש: /admin add <id> | /admin remove <id> | /admin list",
        "en": "Usage: /admin add <id> | /admin remove <id> | /admin list",
    },
    "refresh_running": {
        "he": "מרענן את לוח הזמנים מהאתר…",
        "en": "Refreshing the schedule from the website…",
    },
    "announce_usage": {
        "he": "שימוש: /announce <טקסט ההודעה>",
        "en": "Usage: /announce <message text>",
    },
    "announce_preview": {
        "he": "תצוגה מקדימה של ההודעה לכל הנרשמים:\n\n{text}",
        "en": "Preview of the announcement to all subscribers:\n\n{text}",
    },
    "announce_btn_send": {"he": "שלח לכולם ✅", "en": "Send to all ✅"},
    "announce_btn_cancel": {"he": "ביטול ❌", "en": "Cancel ❌"},
    "announce_sent": {
        "he": "ההודעה נשלחה: {sent} נשלחו, {failed} נכשלו.",
        "en": "Announcement sent: {sent} delivered, {failed} failed.",
    },
    "announce_cancelled": {"he": "ההודעה בוטלה.", "en": "Announcement cancelled."},
    "sched_update_usage": {
        "he": (
            "שימוש: /schedule_update <YYYY-MM-DD> title=<..> time=<HH:MM-HH:MM> "
            "instructor=<..> type=<technical|workshop|milestone|holiday>\n"
            "או: /schedule_update <YYYY-MM-DD> cancel"
        ),
        "en": (
            "Usage: /schedule_update <YYYY-MM-DD> title=<..> time=<HH:MM-HH:MM> "
            "instructor=<..> type=<technical|workshop|milestone|holiday>\n"
            "or: /schedule_update <YYYY-MM-DD> cancel"
        ),
    },
    "sched_update_done": {
        "he": "לוח הזמנים עודכן ({action}) עבור {date}.",
        "en": "Schedule {action} for {date}.",
    },
    "help_header": {"he": "הפקודות הזמינות:", "en": "Available commands:"},
    "help_everyone": {
        "he": (
            "לכולם:\n/start /stop /menu /help /myid\n"
            "שאלות חופשיות: השיעור הבא, לוז, סכם שיעור, הקלטה, שיעורי בית, חומרים מומלצים"
        ),
        "en": (
            "Everyone:\n/start /stop /menu /help /myid\n"
            "Free text: next lesson, schedule, summarize lesson, recording, homework, "
            "recommended materials"
        ),
    },
    "help_admin": {
        "he": "מנהלים:\n/announce /schedule_update + העלאת קובץ לשידור",
        "en": "Admins:\n/announce /schedule_update + upload a file to broadcast",
    },
    "help_owner": {
        "he": "בעלים:\n/map /reindex /refresh_schedule /admin",
        "en": "Owner:\n/map /reindex /refresh_schedule /admin",
    },
}


def detect_language(text: str | None) -> Language:
    """Detect message language from its characters.

    Returns ``he`` if any Hebrew character is present, otherwise ``en``. Falls back to
    the default language for empty input.
    """
    if not text:
        return DEFAULT_LANGUAGE
    if any(ord(ch) in _HEBREW_RANGE for ch in text):
        return "he"
    return "en"


def t(key: str, language: Language) -> str:
    """Translate a catalog key into the requested language.

    Falls back to the default language, then to the key itself, so a missing string is
    visible but never crashes a handler.
    """
    entry = _CATALOG.get(key)
    if entry is None:
        return key
    return entry.get(language) or entry.get(DEFAULT_LANGUAGE) or key
