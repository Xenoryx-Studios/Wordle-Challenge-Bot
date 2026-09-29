import json

DEFAULT_THEME = "default"

THEMES = {
    "default": {
        "name": "default",
        "display_name": "Default",
        "file": "data/wordle_words.json",   # normal Wordle words
        "message": "Today's Wordle starter is **{word}**!",
        "thread_name": "Wordle Thread {date}"
    },

    "halloween": {
        "name": "halloween",
        "display_name": "Halloween",
        "file": "data/wordle_words_halloween.json",
        "message": "🎃 Halloween Wordle! Today's starter is **{word}**!",
        "thread_name": "🎃 Halloween Wordle {date}"
    },

    "christmas": {
        "name": "christmas",
        "display_name": "Christmas",
        "file": "data/wordle_words_christmas.json",
        "message": "🎄 Christmas Wordle! Today's starter is **{word}**!",
        "thread_name": "🎄 Christmas Wordle {date}"
    }
}


def get_theme(name):
    """The named Theme, or the default Theme if the name is unknown."""
    return THEMES.get(name) or THEMES[DEFAULT_THEME]


def available_themes(themes=THEMES):
    """Themes a Server Admin can pick: only those with Starter Words."""
    available = []
    for theme in themes.values():
        try:
            with open(theme["file"], encoding="utf-8") as f:
                if json.load(f):
                    available.append(theme)
        except (OSError, json.JSONDecodeError):
            continue
    return available
