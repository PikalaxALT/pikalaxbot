import asyncio
import json
import os
from collections import defaultdict


class SettingsCategory:
    def __init__(self):
        self.name = self.__class__.__name__.lower()

    def items(self):
        yield from self.__dict__.items()


class Credentials(SettingsCategory):
    token = None
    owner = None


class Meta(SettingsCategory):
    prefix = '!'


class User(SettingsCategory):
    markov_channels = []
    debug = False
    disabled_commands = []
    voice_chans = {}
    disabled_cogs = []
    help_name = 'pikahelp'
    game = '!pikahelp'
    espeak_kw = {
        'a': 100,
        's': 150,
        'v': 'en-us+f3',
        'p': 75
    }
    banlist = []


class Settings:
    credentials = Credentials()
    meta = Meta()
    user = User()
    categories = credentials, meta, user

    def __init__(self, fname='settings.json'):
        self.fname = fname

    def __enter__(self):
        self.fetch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()

    def commit(self):
        data = defaultdict(dict)
        print(*self.categories)
        for cat in self.categories:
            for key, value in cat.items():
                if isinstance(value, set):
                    value = list(value)
                data[cat.name][key] = value
        with open(self.fname, 'w') as fp:
            json.dump(data, fp, separators=(', ', ': '), indent=4)

    def fetch(self):
        mode = 'r' if os.path.exists(self.fname) else 'w+'
        if os.path.dirname(self.fname) and not os.path.exists(os.path.dirname(self.fname)):
            os.makedirs(os.path.dirname(self.fname), exist_ok=True)
        with open(self.fname, mode=mode) as fp:
            data = json.load(fp)
        for cat, grp in data.items():
            obj = getattr(self, cat)
            for key, value in grp.items():
                setattr(obj, key, value)
