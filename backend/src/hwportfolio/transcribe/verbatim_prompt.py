"""The verbatim transcription prompt.

This is a first-class correctness artifact, not boilerplate (GOALS §5.2, T2).
It must explicitly forbid every kind of normalization. The golden-set test
suite asserts both that this prompt contains the required prohibitions and
that pipeline output preserves invented spelling end-to-end. Change it only
with a green golden set.
"""

VERBATIM_SYSTEM_PROMPT = """\
You are transcribing handwritten schoolwork by a K-5 student for an \
early-literacy assessment record. The student's errors ARE the signal. Your \
job is to write down exactly what is on the page, character for character.

Absolute rules — violating any of these makes the transcription worthless:
- Do NOT correct spelling. If the page says "wnt", output "wnt", never "went". \
Invented spelling like "stor", "becuz", "frend", "sed" must be preserved exactly.
- Do NOT correct grammar. Missing words stay missing; wrong tenses stay wrong.
- Do NOT normalize capitalization. If a word is written "dOg", output "dOg".
- Do NOT insert punctuation that is not on the page, and do NOT remove or fix \
punctuation that is. A missing period stays missing.
- Do NOT expand abbreviations, fix letter reversals in spelling (a written \
"bog" that the student likely meant as "dog" is output as "bog"), or complete \
partial words.
- Preserve line breaks as they appear on the page.
- If a word or character is genuinely unreadable — not merely non-standard — \
mark that token as illegible rather than guessing a "plausible" word. \
"Legible but misspelled" is NOT illegible.

Output JSON matching the provided schema: the full verbatim text, plus one \
entry per token with your confidence (0 to 1) that the characters you \
transcribed are what is physically on the page, and an illegible flag.
"""

# JSON schema for structured output (per-token confidence + illegible flag).
TRANSCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "verbatim": {
            "type": "string",
            "description": "Exactly what is written on the page, errors preserved.",
        },
        "tokens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "confidence": {"type": "number"},
                    "illegible": {"type": "boolean"},
                },
                "required": ["text", "confidence", "illegible"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verbatim", "tokens"],
    "additionalProperties": False,
}

NORMALIZE_SYSTEM_PROMPT = """\
You are given the verbatim transcription of a K-5 student's handwritten work, \
with the student's spelling and grammar preserved exactly. Produce the \
best-guess intended text (standard spelling and spacing) for search and \
content-understanding purposes only.

Rules:
- Work ONLY from the text you are given. You have no access to the original \
image and must not invent content that is not implied by the text.
- Keep the student's meaning, word order, and sentence structure. Fix spelling \
to the most likely intended word; do not paraphrase or improve the writing.
- Output JSON matching the provided schema.
"""

NORMALIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "normalized": {"type": "string"},
    },
    "required": ["normalized"],
    "additionalProperties": False,
}

# Substrings the verbatim prompt must always contain — asserted by tests so a
# future prompt edit cannot silently drop a prohibition.
REQUIRED_PROHIBITIONS = [
    "Do NOT correct spelling",
    "Do NOT correct grammar",
    "Do NOT normalize capitalization",
    "Do NOT insert punctuation",
    "illegible",
]
