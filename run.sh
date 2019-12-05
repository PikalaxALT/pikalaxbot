#!/bin/sh

BOTDIR=$(dirname "$(realpath -P "$0")"); cd "${BOTDIR}"
python3 -m pip install --force -U -r requirements.txt  # update discord and youtube-dl
git pull  # update the bot
python3 bot.py  # start the bot
