"""Indian document validation rules (real, checkable algorithms).

Aadhaar: 12 digits, first digit 2-9, last digit a Verhoeff check digit
(UIDAI/NPCI standard — tables per the canonical Verhoeff algorithm).
PAN: AAA + holder-type letter + surname-initial letter + 4 digits + check
letter (Income Tax Department structure).
"""

# Verhoeff tables (dihedral group D5 multiplication, position permutation,
# inverse)
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def _verhoeff_c(number: str) -> int:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c


def aadhaar_check_digit(first_11_digits: str) -> str:
    """Compute the correct 12th digit for an Aadhaar number."""
    return str(_INV[_verhoeff_c(first_11_digits + "0")])


def aadhaar_valid(number: str) -> bool:
    return _verhoeff_c(number) == 0


PAN_HOLDER_TYPES = {
    "A": "Association of Persons", "B": "Body of Individuals", "C": "Company",
    "F": "Firm", "G": "Government", "H": "Hindu Undivided Family",
    "L": "Local Authority", "J": "Artificial Juridical Person",
    "P": "Individual", "T": "Trust",
}


def pan_structure_ok(pan: str) -> bool:
    """Basic PAN structure: 5 letters, 4 digits, 1 letter (AAAPL1234K)."""
    import re
    return bool(re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan.upper().strip()))


def pan_holder_type(pan: str) -> str | None:
    """Meaning of the 4th character (holder type), if structured."""
    pan = pan.upper().strip()
    if pan_structure_ok(pan):
        return PAN_HOLDER_TYPES.get(pan[3])
    return None


def pan_surname_initial(pan: str) -> str | None:
    """The 5th character — first letter of the holder's surname."""
    pan = pan.upper().strip()
    if pan_structure_ok(pan):
        return pan[4]
    return None
