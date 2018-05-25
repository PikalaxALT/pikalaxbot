import json
import os


class Settings:
    def __init__(self, fname='settings.json'):
        self.fname = fname
        self.data: dict = {}

    def __enter__(self):
        self.fetch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()
        self.data = {}

    def commit(self):
        with open(self.fname, 'w') as fp:
            json.dump(self.data, fp, separators=(', ', ': '), indent=4)

    def fetch(self):
        mode = 'r' if os.path.exists(self.fname) else 'w+'
        if os.path.dirname(self.fname) and not os.path.exists(os.path.dirname(self.fname)):
            os.makedirs(os.path.dirname(self.fname), exist_ok=True)
        with open(self.fname, mode=mode) as fp:
            self.data = json.load(fp)
        self.data.setdefault('credentials', {})
        self.data.setdefault('user', {})
        self.data.setdefault('meta', {})
        self.data['user'].setdefault('markov_channels', [])
        self.data['user'].setdefault('game', '!pikahelp')
        self.data['user'].setdefault('whitelist', [])
        self.data['user'].setdefault('debug', False)
        self.data['user'].setdefault('cooldown', 10)

    def set(self, group, key, value):
        self.data[group][key] = value

    def get(self, group, key, default=None):
        return self.data[group].get(key, default)

    def items(self, group):
        yield from self.data[group].items()

    def keys(self, group):
        yield from self.data[group].keys()

    def values(self, group):
        yield from self.data[group].values()

    def add_markov_channel(self, ch_id):
        markov_channels = set(self.data['user']['markov_channels'])
        if ch_id in markov_channels:
            return False
        markov_channels.add(ch_id)
        self.set('user', 'markov_channels', list(markov_channels))
        return True

    def del_markov_channel(self, ch_id):
        markov_channels = set(self.data['user']['markov_channels'])
        if ch_id not in markov_channels:
            return False
        markov_channels.remove(ch_id)
        self.set('user', 'markov_channels', list(markov_channels))
        return True
