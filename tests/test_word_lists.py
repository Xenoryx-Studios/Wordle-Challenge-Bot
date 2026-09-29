import json
from pathlib import Path

import pytest

from core.themes import THEMES

ACCEPTED_GUESSES_FILE = Path(__file__).parent / "data" / "nyt_accepted_guesses.txt"


def _accepted_guesses():
    lines = ACCEPTED_GUESSES_FILE.read_text(encoding="utf-8").splitlines()
    return {line.strip().upper() for line in lines if line.strip() and not line.startswith("#")}


@pytest.mark.parametrize("theme_name", sorted(THEMES))
def test_every_starter_word_is_an_accepted_guess(theme_name):
    # Every Starter Word must be a guess the NYT Wordle accepts, or members
    # cannot open with it (see CONTEXT.md).
    with open(THEMES[theme_name]["file"], encoding="utf-8") as f:
        words = [w.upper() for w in json.load(f)]

    rejected = sorted(set(words) - _accepted_guesses())

    assert not rejected, f"{theme_name} word list has words that are not accepted guesses: {rejected}"
