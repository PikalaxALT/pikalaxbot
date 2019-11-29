#!/bin/sh

cd /home/pi/pikalaxbot/
pip install -U -r requirements.txt  # update discord and youtube-dl
git pull  # update the bot
python3 bot.py  # start the bot
