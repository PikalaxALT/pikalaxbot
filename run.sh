#!/bin/sh

BOTDIR=$(dirname "$(realpath -P "$0")"); cd "${BOTDIR}"
git pull  # update the bot
python3 -m pip install -U -r requirements.txt  # update discord
python3 -m pikalaxbot  # start the bot
