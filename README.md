[![PyPI](https://img.shields.io/badge/discord.py-1.7.1-green.svg)](https://github.com/Rapptz/discord.py/tree/master/) \
[![PyPI](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-395/) \
[![PyPI](https://img.shields.io/badge/support-discord-lightgrey.svg)](https://discord.gg/TbjzpzR9Rg)

# PikalaxBOT
Combination Discord Bot and Twitch WIP Bot.

## Requirements
Python >= 3.9 is required. FFMPEG and libsodium are required for voice. \
Linux users may need to install their distributions' `python3-matplotlib` package as well, instead of using `pip`.

## Setup

1) Clone this repository (duh).
2) Create a `settings.json` using the following template.
3) Install the requirements using `python -m pip install -U -r requirements.txt`.
- See note above about matplotlib.
4) Set up a database in postgresql, and fill in your credentials in the `settings.json` file under "database".
5) Run bot.py using `python bot.py`.
```json
{
    "token": "My Discord Bot Token",
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
    "exc_channel": 657960851193724960,
    "database": {
        "username": "root", 
        "password": "raspberrypi", 
        "host": "localhost", 
        "dbname": "pikalaxbot"
    }
}
```
