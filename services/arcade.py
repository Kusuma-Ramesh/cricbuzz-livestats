"""Pure grading and feedback helpers for the Stat Arcade games (no Streamlit, so they are unit-testable).

Every feedback string is self-contained: it names the round it describes (both players / the match and
the guess), so it can never be mistaken for feedback about the question currently on screen.
"""

from __future__ import annotations


def grade_total_guess(guess: int, actual: int) -> dict:
    """Grade a Guess-the-Total answer. One dict feeds the XP, the message and the score, so they always agree."""
    guess, actual = int(guess), int(actual)
    err = abs(guess - actual)
    return {"guess": guess, "actual": actual, "err": err, "pts": max(0, 50 - err)}


def total_feedback(description: str, result: dict) -> str:
    """Feedback for a finished Guess-the-Total round, naming the match and both numbers."""
    return (
        f"Last round ({description}): you guessed {result['guess']}, the actual total was "
        f"{result['actual']} - {result['err']} off. +{result['pts']} XP"
    )


def grade_higher_lower(runs_a: int, runs_b: int, guess: str) -> bool:
    """True when 'higher'/'lower' correctly predicts B's career runs relative to A's (ties count as higher)."""
    return (int(runs_b) >= int(runs_a)) == (guess == "higher")


def higher_lower_feedback(pa: dict, pb: dict, guess: str, right: bool, gain: int) -> str:
    """Feedback for a finished Higher-or-Lower round, naming both players, their runs and what the guess meant.

    'Higher' / 'Lower' always refers to the HIDDEN player (pb) compared with the SHOWN player (pa).
    """
    ra, rb = int(pa["runs"]), int(pb["runs"])
    facts = f"{pa['full_name']} {ra:,} runs vs {pb['full_name']} {rb:,} runs"
    meaning = "more" if guess == "higher" else "fewer"
    verdict = f"Correct! +{gain} XP" if right else "Not quite."
    tie = " Equal runs count as higher." if ra == rb else ""
    return (
        f"Last round ({facts}): you said {guess}, i.e. {pb['full_name']} would have "
        f"{meaning} career runs than {pa['full_name']}.{tie} {verdict}"
    )