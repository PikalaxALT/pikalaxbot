[![PyPI](https://img.shields.io/badge/discord.py-1.3.0a-green.svg)](https://github.com/Rapptz/discord.py/tree/master/) \
[![PyPI](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-375/) \
[![PyPI](https://img.shields.io/badge/support-discord-lightgrey.svg)](https://discord.gg/dpy)

# PikalaxBOT

## Requirements
Python >= 3.7 is required. FFMPEG and libsodium are required for voice.

## Setup

1) Clone this repository (duh).
2) Create a settings.json using the following template.
3) Install the requirements using `python3.7 -m pip install -r requirements.txt`.
4) Run bot.py using `python3.7 bot.py`.
```json
{
    "token": "My Bot Token",
    "prefix": "p!",
    "markov_channels": [],
    "debug": false,
    "disabled_commands": [],
    "voice_chans": {},
    "disabled_cogs": [],
    "help_name": "help",
    "game": "p!help",
    "espeak_kw": {
        "a": 100,
        "s": 150,
        "v": "en-us+f3",
        "p": 75,
        "g": 1,
        "k": 2
    },
    "banlist": [],
    "roles": {},
    "watches": {},
    "error_emoji": "pikalaOwO",
    "exc_channel": 657960851193724960
}
```
