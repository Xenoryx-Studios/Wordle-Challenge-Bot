import json
from collections import Counter
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


@pytest.mark.parametrize("theme_name", sorted(THEMES))
def test_word_lists_have_unique_five_letter_words(theme_name):
    with open(THEMES[theme_name]["file"], encoding="utf-8") as f:
        words = [w.upper() for w in json.load(f)]

    wrong_length = sorted(w for w in words if len(w) != 5)
    duplicates = sorted(w for w, count in Counter(words).items() if count > 1)

    assert not wrong_length, f"{theme_name} word list has words that are not five letters: {wrong_length}"
    assert not duplicates, f"{theme_name} word list has duplicate words: {duplicates}"


def test_themes_without_words_are_not_available(tmp_path):
    from core.themes import available_themes

    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    full = tmp_path / "full.json"
    full.write_text('["ghost"]', encoding="utf-8")
    themes = {"a": {"name": "a", "file": str(empty)}, "b": {"name": "b", "file": str(full)},
              "c": {"name": "c", "file": str(tmp_path / "missing.json")}}

    assert [t["name"] for t in available_themes(themes)] == ["b"]
