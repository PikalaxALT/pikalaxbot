#!/bin/sh -xe

prevdir=$(pwd)
BOTDIR=$(dirname "$(realpath -P "$0")"); cd "${BOTDIR}"

# Update pokeapi
git pull  # update the bot
python3 -m pip install -U -r requirements.txt  # update discord
if [ -f setup_pokeapi.sh ]; then ./setup_pokeapi.sh; fi
JISHAKU_NO_UNDERSCORE=true \
JISHAKU_NO_DM_TRACEBACK=true \
python3 -m pikalaxbot  # start the bot

cd $prevdir
