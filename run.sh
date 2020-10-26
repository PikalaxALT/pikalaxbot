#!/bin/sh

BOTDIR=$(dirname "$(realpath -P "$0")"); cd "${BOTDIR}"

# Update pokeapi
git pull  # update the bot
if ! [ -d pokeapi ]; then
  git submodule init
fi
git submodule update --remote
python3 -m pip install -U -r requirements.txt  # update discord
JISHAKU_NO_UNDERSCORE=true JISHAKU_NO_DM_TRACEBACK=true python3 -m pikalaxbot  # start the bot
