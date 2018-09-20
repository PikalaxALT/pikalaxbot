[![PyPI](https://img.shields.io/badge/discord.py-1.0.0a-green.svg)](https://github.com/Rapptz/discord.py/tree/rewrite/) \
[![PyPI](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-364/) \
[![PyPI](https://img.shields.io/badge/support-discord-lightgrey.svg)](https://discord.gg/hhVjAN8)

# PikalaxBOT

## Setup

1) Clone this repository (duh).
2) Create a settings.json using the following template.
3) Install the requirements using `python3.6 -m pip install -r requirements.txt`.
4) Run bot.py using `python3.6 bot.py`.
```
{
    "meta": {
        "prefix": "<command_prefix>"
    },
    "credentials": {
        "owner": "<your_id>",
        "token": "<bot_oauth>"
    },
    "user": {
        "debug": <true or false>,
        "voice_chans": [list of voice channel IDs],
        "markov_channels": [list of text channel IDs],
        "help_name": "<name for help command>",
        "game": "<activity to display as playing>",
        "espeak_kw": {
            "a": amplitude,
            "s": speed,
            "v": "<voice code>",
            "p": pitch,
            "k": capital pitch modulation,
            "g": gap between words
        }
    }
}
```
