import json


class Settings:
    def __init__(self, fname='settings.json'):
        self.fname = fname
        self.data: dict = {}

    def __enter__(self):
        with open(self.fname) as fp:
            self.data = json.load(fp)
        self.data.setdefault('credentials', {})
        self.data.setdefault('user', {})
        self.data.setdefault('meta', {})
        self.data['user'].setdefault('markov_channels', [])
        self.data['user'].setdefault('game', '!pikahelp')
        self.data['user'].setdefault('whitelist', {})
        self.data['user'].setdefault('debug', False)
        self.data['user'].setdefault('cooldown', 10)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with open(self.fname, 'w') as fp:
            json.dump(self.data, fp, separators=(', ', ': '), indent=4)
        self.data = {}

    def set(self, group, key, value):
        self.data[group][key] = value

    def get(self, group, key, default=None):
        return self.data[group].get(key, default=default)

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
        if ch_id in markov_channels:
            return False
        markov_channels.remove(ch_id)
        self.set('user', 'markov_channels', list(markov_channels))
        return True
