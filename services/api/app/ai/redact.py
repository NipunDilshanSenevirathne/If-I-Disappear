"""The no-secrets pipeline.

Secrets (PINs, passwords, one-time codes, card numbers, full account numbers)
are never stored, never shown and never sent to a model as text. Typed text is
redacted before anything else happens. Transcripts and readings are redacted
again after the model returns them (the model is also told to remove secrets).
Phone numbers are masked down to their last four digits.

Redaction is deliberately conservative: it would rather hide a harmless number
than keep a secret. The household sees "[secret removed]" and a count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SECRET = "[secret removed]"

# Numeric secrets need digits after the keyword ("PIN 4821", "OTP: 552 901").
_DIGIT_KEYS = (
    r"(?:\b(?:pin(?:\s*(?:number|code|no\.?))?|otp|one[-\s]?time\s*(?:code|password)|security\s*code|cvv|cvc"
    r"|(?:verification|authentication|auth|access|login|sign[-\s]?in|confirmation)\s*code)\b)"
)
_DIGIT_SECRET = re.compile(
    rf"(?P<lead>{_DIGIT_KEYS}\s*(?:is|was|:|=|-)?\s*)(?P<secret>\d[\d\s-]{{2,}}\d|\d{{3,}})",
    re.IGNORECASE,
)
# Word secrets need a connector ("password is ...", "password: ...") so that
# "the password box" isn't redacted, but "my password is hunter22" is.
_WORD_KEYS = r"(?:\b(?:password|passcode|pass\s*word|security\s*answer)\b)"
_WORD_SECRET = re.compile(
    rf"(?P<lead>{_WORD_KEYS}\s*(?:is|was|:|=)\s*)(?P<secret>(?!\[secret removed\])[^\s,;!?]+?)(?=[.,;!?]?(?:\s|$))",
    re.IGNORECASE,
)
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
# Sri Lankan style numbers: +94 or 0, then nine digits in any grouping (077 123 4567, 0812 223 344).
_PHONE = re.compile(r"(?<![\w-])(?P<prefix>\+94[\s-]?|0)(?P<rest>\d(?:[\s-]?\d){8})(?![\w-])")
_LONG_NUMBER = re.compile(r"\b\d{9,}\b")


@dataclass
class Redaction:
    text: str
    secrets_removed: int
    phones_masked: int


def mask_phone(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group("rest"))
    lead = "+94 " if match.group("prefix").startswith("+94") else "0"
    return f"{lead}{digits[:2]}-XXX-{digits[-4:]}"


def redact(text: str) -> Redaction:
    if not text:
        return Redaction(text or "", 0, 0)
    count = 0

    def _secret(m: re.Match) -> str:
        nonlocal count
        count += 1
        return m.group("lead") + SECRET

    out = _WORD_SECRET.sub(_secret, text)
    out = _DIGIT_SECRET.sub(_secret, out)

    def _card(m: re.Match) -> str:
        nonlocal count
        count += 1
        return SECRET

    out = _CARD.sub(_card, out)
    phones = 0

    def _phone(m: re.Match) -> str:
        nonlocal phones
        phones += 1
        return mask_phone(m)

    out = _PHONE.sub(_phone, out)

    def _long(m: re.Match) -> str:
        nonlocal count
        count += 1
        return SECRET

    out = _LONG_NUMBER.sub(_long, out)
    return Redaction(out, count, phones)


def contains_secret(text: str) -> bool:
    return redact(text).secrets_removed > 0
