---
name: discussion-voice
description: >-
  Write and de-slop Canvas discussion replies in the instructor's voice.
  Use when generating, editing, or reviewing professor replies to student
  discussion posts; when replies sound like AI, ChatGPT, corporate, generic,
  or a grading comment; or when the user asks to humanize, de-slop, or match
  their Canvas voice.
---

# Discussion voice

Discussion replies go through `chcp/llm/response_generator.py`. Match
[config/VOICE.md](../../../config/VOICE.md). Method adapted from
[humanizer](https://github.com/hannsxpeter/humanizer): voice first, then tell
removal, then restraint. Do not add facts to sound concrete. This is quality
and voice, not detector evasion.

## When drafting or rewriting a reply

1. Read `config/VOICE.md`.
2. Write in that cadence before stripping tells.
3. React to one specific claim. Add one physics step. Stop.
4. Uneven sentence lengths. Do not recap, grade, or close with "this will help in your field."
5. Allowed at most once, only if they fit: "I dig that", "spot on", "on point", "excellent", "100% agree".
6. Never invent a story, number, quote, or cause the student did not give.

## Dead-giveaway tells to cut

- "Great job identifying" / "You've correctly explained" / "Excellent comprehensive explanation"
- "This understanding is crucial" / "this will help you in your field"
- "It's important to note" / "delve" / "tapestry" / "at its core"

If a stored example in `config/courses.json` sounds like those, do not use it as a voice model. The pipeline already filters them.

## Output

Return the reply text a student would see. No rubric commentary. No name-lead if you are only rewriting a body that code will assemble.
