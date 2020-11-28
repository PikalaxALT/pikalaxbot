#!/bin/sh -xe

prevdir=$(pwd)
BOTDIR=$(dirname "$(realpath -P "$0")"); cd "${BOTDIR}"

if ! [ -d pokeapi ]; then
  git submodule init
fi
git submodule update --recursive
cd pokeapi
# shellcheck disable=SC2039
python3 -m pip install -U -r <(grep -v psycopg2 requirements.txt)
python3 -m pip install -U psycopg2
make setup
python3 manage.py shell -c "from data.v2.build import build_all; build_all()" --settings=config.local

cd "$prevdir"
