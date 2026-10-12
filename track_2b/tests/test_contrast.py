"""Every text/background pair of the design tokens meets WCAG AA in both themes (spec 13.4)."""

import re
from pathlib import Path

import pytest

TOKENS = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "lib" / "design" / "tokens.css").read_text()


def parse(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--bk-[\w-]+):\s*([^;]+);", block))


LIGHT = parse(TOKENS.split("@media (prefers-color-scheme: dark)")[0])
DARK = {**LIGHT, **parse(TOKENS.split("@media (prefers-color-scheme: dark)")[1].split("@media (prefers-reduced-motion")[0])}


def rgba(value: str) -> tuple[float, float, float, float]:
    value = value.strip()
    if value.startswith("#"):
        return (*(int(value[i : i + 2], 16) for i in (1, 3, 5)), 1.0)
    r, g, b, a = (float(x) for x in re.findall(r"[\d.]+", value))
    return r, g, b, a


def over(top: str, bottom: str) -> tuple[float, float, float]:
    r, g, b, a = rgba(top)
    br, bg, bb, _ = rgba(bottom)
    return (r * a + br * (1 - a), g * a + bg * (1 - a), b * a + bb * (1 - a))


def luminance(colour: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground: str, background: tuple[float, float, float]) -> float:
    a, b = sorted((luminance(over(foreground, "#000000")), luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# (text token, background token, optional wash between them, minimum ratio)
PAIRS = [
    ("--bk-ink", "--bk-paper", None, 4.5), ("--bk-ink", "--bk-surface", None, 4.5),
    ("--bk-ink-2", "--bk-paper", None, 4.5), ("--bk-ink-2", "--bk-surface", None, 4.5),
    ("--bk-teal", "--bk-paper", None, 4.5), ("--bk-teal", "--bk-surface", None, 4.5),
    ("--bk-amber", "--bk-paper", None, 4.5), ("--bk-amber", "--bk-surface", None, 4.5),
    ("--bk-amber", "--bk-paper", "--bk-amber-wash", 4.5), ("--bk-amber", "--bk-surface", "--bk-amber-wash", 4.5),
    ("--bk-red", "--bk-paper", None, 4.5), ("--bk-red", "--bk-surface", None, 4.5),
    ("--bk-ink", "--bk-paper", "--bk-teal-wash", 4.5), ("--bk-ink", "--bk-surface", "--bk-teal-wash", 4.5),
    ("--bk-ink", "--bk-paper", "--bk-red-wash", 4.5), ("--bk-ink-2", "--bk-paper", "--bk-red-wash", 4.5),
    ("--bk-on-teal", "--bk-teal", None, 4.5),
    ("--bk-green", "--bk-surface", None, 3.0),  # the language light is a mark next to a text label, not text
    ("--bk-red", "--bk-paper", "--bk-red-wash", 3.0),  # large heading (24 px) on the warning card
]


@pytest.mark.parametrize("theme,tokens", [("light", LIGHT), ("dark", DARK)])
@pytest.mark.parametrize("text,background,wash,minimum", PAIRS)
def test_contrast(theme, tokens, text, background, wash, minimum):
    base = over(tokens[background], "#000000")
    if wash:
        r, g, b = over(tokens[wash], "#%02x%02x%02x" % tuple(round(c) for c in base))
        base = (r, g, b)
    ratio = contrast(tokens[text], base)
    assert ratio >= minimum, f"{theme}: {text} on {background}{' + ' + wash if wash else ''} is {ratio:.2f}:1"
