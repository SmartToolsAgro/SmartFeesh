"""Amounts in French words, as Tunisian invoices state them (D-125).

"Arrêtée la présente facture à la somme de : Trois mille cinq cent quinze Dinars 500 Millimes". Traditional
spelling (hyphens below one hundred, "et un", "quatre-vingts", "deux cents", "mille" invariable).
"""

from decimal import ROUND_HALF_UP, Decimal

_UNITS = [
    "zéro",
    "un",
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
    "dix",
    "onze",
    "douze",
    "treize",
    "quatorze",
    "quinze",
    "seize",
]
_TENS = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _below_100(number: int, *, last: bool) -> str:
    """0 < number < 100. `last`: nothing follows, so "quatre-vingts" takes its "s"."""
    if number <= 16:
        return _UNITS[number]
    if number < 20:
        return f"dix-{_UNITS[number - 10]}"
    tens, unit = divmod(number, 10)
    if tens in (7, 9):
        # 70-79 and 90-99 count on from sixty and eighty: soixante-douze, quatre-vingt-dix-sept.
        base = "soixante" if tens == 7 else "quatre-vingt"
        rest = number - (60 if tens == 7 else 80)
        joiner = " et " if rest == 11 and tens == 7 else "-"
        return f"{base}{joiner}{_below_100(rest, last=True)}"
    if tens == 8:
        return ("quatre-vingts" if last else "quatre-vingt") if unit == 0 else f"quatre-vingt-{_UNITS[unit]}"
    if unit == 0:
        return _TENS[tens]
    joiner = " et " if unit == 1 else "-"
    return f"{_TENS[tens]}{joiner}{_UNITS[unit]}"


def _below_1000(number: int, *, last: bool) -> str:
    """0 < number < 1000."""
    hundreds, rest = divmod(number, 100)
    parts: list[str] = []
    if hundreds:
        if hundreds == 1:
            parts.append("cent")
        else:
            # "deux cents" alone, "deux cent trois" and "deux cent mille" otherwise.
            parts.append(f"{_UNITS[hundreds]} cent{'s' if rest == 0 and last else ''}")
    if rest:
        parts.append(_below_100(rest, last=last))
    return " ".join(parts)


def number_in_words(number: int) -> str:
    """A whole number from 0 up, in French words: 3515 → "trois mille cinq cent quinze"."""
    if number < 0:
        raise ValueError("number_in_words expects a positive number")
    if number == 0:
        return _UNITS[0]
    parts: list[str] = []
    for value, singular, plural in ((10**9, "milliard", "milliards"), (10**6, "million", "millions")):
        count, number = divmod(number, value)
        if count:
            parts.append(f"{number_in_words(count)} {singular if count == 1 else plural}")
    thousands, number = divmod(number, 1000)
    if thousands:
        # "mille", never "un mille"; mille never takes an "s".
        parts.append("mille" if thousands == 1 else f"{_below_1000(thousands, last=False)} mille")
    if number:
        parts.append(_below_1000(number, last=True))
    return " ".join(parts)


def dinars_in_words(amount: Decimal) -> str:
    """An amount in dinars as printed on an invoice: "Trois mille cinq cent quinze Dinars 500 Millimes"."""
    millimes_total = int(Decimal(amount).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP) * 1000)
    if millimes_total < 0:
        raise ValueError("dinars_in_words expects a positive amount")
    dinars, millimes = divmod(millimes_total, 1000)
    text = f"{number_in_words(dinars)} {'Dinar' if dinars <= 1 else 'Dinars'}"
    if millimes:
        text += f" {millimes:03d} Millimes"
    return text[0].upper() + text[1:]
