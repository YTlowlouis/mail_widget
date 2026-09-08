"""Extraction déterministe (regex) d'un code OTP/vérification dans un corps de mail.

Jamais confiée au modèle, comme SPF/DKIM/DMARC: soit le code est trouvé par une règle
simple et explicable, soit rien n'est proposé — jamais une valeur devinée.
"""
from __future__ import annotations

import re

_KEYWORD_RE = re.compile(
    r"(code|otp|verification|v[ée]rification|one[- ]time|confirm|s[ée]curit[ée]|security|authentif)",
    re.IGNORECASE,
)
_CODE_RE = re.compile(r"(?<!\d)(\d[\d ]{2,7}\d)(?!\d)")

_MIN_DIGITS = 4
_MAX_DIGITS = 8
_KEYWORD_WINDOW_BEFORE = 40
_KEYWORD_WINDOW_AFTER = 10


def extract_otp_code(body_text: str) -> str | None:
    """Retourne le premier code plausible (4 à 8 chiffres) trouvé près d'un mot-clé lié à
    la vérification/l'authentification. Sans mot-clé à proximité, ne retourne rien plutôt
    que de risquer de copier un numéro qui n'est pas un code (année, montant, identifiant)."""
    for match in _CODE_RE.finditer(body_text):
        digits = match.group(1).replace(" ", "")
        if not (_MIN_DIGITS <= len(digits) <= _MAX_DIGITS):
            continue
        window_start = max(0, match.start() - _KEYWORD_WINDOW_BEFORE)
        window_end = min(len(body_text), match.end() + _KEYWORD_WINDOW_AFTER)
        if _KEYWORD_RE.search(body_text[window_start:window_end]):
            return digits
    return None
