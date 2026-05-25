"""Build the student submission section of the LLM grading prompt."""

from __future__ import annotations

from chcp.grading.analysis import SubmissionAnalysis
from chcp.submission_models import DiscussionSubmission


def format_grading_brief(
    analysis: SubmissionAnalysis,
    discussion_prompt: str,
) -> str:
    """
    Rich grading packet: prompt, automated checklist, then full student text.

    Gives the LLM the same facts enforcement will use so scores align with policy.
    """
    sub = analysis.submission
    lines = [
        "=== DISCUSSION PROMPT (what the student must address) ===",
        discussion_prompt.strip() or "(no prompt configured)",
        "",
        "=== AUTOMATED PRE-GRADE CHECKLIST (verify; do not contradict without reason) ===",
    ]
    lines.extend(f"- {item}" for item in analysis.checklist)
    lines.extend(
        [
            "",
            f"Comprehension note: {analysis.comprehension_summary}",
            f"Engagement note: {analysis.engagement_summary}",
            f"Writing note: {analysis.writing_summary}",
            f"Timeliness note: {analysis.timeliness_summary}",
        ]
    )

    if analysis.citation_report.signal_labels:
        lines.append("")
        lines.append("Citation signals detected:")
        for label in analysis.citation_report.signal_labels[:12]:
            lines.append(f"  • {label}")
        if len(analysis.citation_report.signal_labels) > 12:
            lines.append(f"  • … and {len(analysis.citation_report.signal_labels) - 12} more")

    lines.extend(["", "=== INITIAL POST (student's main response) ==="])
    lines.append(sub.initial_post.strip() or "(empty)")

    lines.append("")
    lines.append(
        f"=== PEER REPLIES TO CLASSMATES ({len(analysis.peer_replies)} detected) ==="
    )
    if not analysis.peer_replies:
        lines.append("(none — Engagement should be below per rubric)")
    else:
        for peer in analysis.peer_replies:
            flags = []
            if peer.greets_classmate:
                flags.append("greets classmate")
            flags.append(
                "meaningful" if peer.is_meaningful else f"short (<{analysis.min_peer_reply_chars} chars)"
            )
            if peer.qualifies_for_exceeds_engagement:
                flags.append("exceeds-quality dialogue")
            elif peer.is_substantive:
                flags.append("substantive")
            else:
                flags.append("agreement-only/thin")
            lines.append(
                f"--- Reply {peer.index} ({peer.char_count} chars, "
                f"{peer.word_count} words; {', '.join(flags)}) ---"
            )
            lines.append(peer.text or "(empty)")

    lines.append("")
    if sub.days_late is not None:
        lines.append(f"Canvas days late: {sub.days_late}")
    else:
        lines.append(
            f"Late indicator in preview: {'yes' if sub.is_late else 'no'}"
        )

    if sub.link_urls:
        lines.append("")
        lines.append("=== LINKS FROM POST (count as citations) ===")
        for url in sub.link_urls:
            lines.append(url)

    lines.extend(
        [
            "",
            "=== GRADING INSTRUCTIONS FOR THIS SUBMISSION ===",
            "1. Comprehension: Judge ONLY the initial post against the discussion prompt — "
            "organization, critical thinking, examples, and depth.",
            "2. Timeliness: Use the timeliness note above; do not assign exceeds for timeliness.",
            "3. Engagement: Judge EACH peer reply. Exceeds when two replies greet a classmate and "
            "discuss the topic/field (see exceeds-quality flags). Meets for two thinner replies; zero → below.",
            "4. Writing: Clarity and grammar. Exceeds when writing is clear and a real source is cited "
            "(URL, References list, or Author (Year). Title (ed.). Publisher). Meets when clear but no source.",
            "Reference the checklist in each criterion reason when your level differs from a hint.",
        ]
    )
    return "\n".join(lines)


def format_submission_for_prompt(submission: DiscussionSubmission) -> str:
    """Legacy formatter without analysis (prefer format_grading_brief)."""
    from chcp.grading.analysis import analyze_submission

    analysis = analyze_submission(submission)
    return format_grading_brief(analysis, discussion_prompt="")
