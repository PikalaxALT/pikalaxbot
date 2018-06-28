#!/bin/sh

pip install -U -r requirements.txt  # update discord and youtube-dl
git pull  # update the bot
python3.6 bot.py  # start the bot
