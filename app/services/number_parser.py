import re

# 0-9 only (\d also takes other scripts' digits): the browser reads the same
# strings with web/js/ui.js parseQuantity — keep the two in step.
_CLEAN_RE = re.compile(r"^\s*([0-9.,]+)\s*([kKmM]?)\s*$")


def parse_quantity(raw: str) -> float:
    """Parses values like '25.7k', '1,8k', '32000', '32.000', '1500' into a float.

    Rule: a trailing k/m multiplies by 1,000/1,000,000, and any comma is treated
    as a decimal separator. Without a k/m suffix, a single dot followed by
    exactly 3 digits is treated as a thousands separator (pt-BR convention),
    since that's the only case a suffix-less input is ambiguous.
    """
    if raw is None:
        raise ValueError("valor vazio")

    match = _CLEAN_RE.match(raw)
    if not match:
        raise ValueError(f"não consegui interpretar o valor: {raw!r}")

    number_part, suffix = match.groups()

    if suffix:
        number_part = number_part.replace(",", ".")
        if number_part.count(".") > 1:
            raise ValueError(f"não consegui interpretar o valor: {raw!r}")
        value = float(number_part)
        return value * (1_000 if suffix.lower() == "k" else 1_000_000)

    if "," in number_part and "." in number_part:
        raise ValueError(f"não consegui interpretar o valor: {raw!r}")

    if "," in number_part:
        number_part = number_part.replace(",", ".")
        return float(number_part)

    if number_part.count(".") == 1:
        integer_part, decimal_part = number_part.split(".")
        if len(decimal_part) == 3:
            return float(integer_part + decimal_part)
        return float(number_part)

    if number_part.count(".") > 1:
        raise ValueError(f"não consegui interpretar o valor: {raw!r}")

    return float(number_part)
