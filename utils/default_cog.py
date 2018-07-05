from utils.botclass import PikalaxBOT


class Cog:
    config_attrs = tuple()

    def __init__(self, bot):
        self.bot: PikalaxBOT = bot

    async def fetch(self):
        with self.bot.settings as settings:
            for attr in self.config_attrs:
                val = getattr(settings.user, attr)
                if isinstance(val, list):
                    val = set(val)
                setattr(self, attr, val)

    async def commit(self):
        with self.bot.settings as settings:
            for attr in self.config_attrs:
                val = getattr(self, attr)
                if isinstance(val, set):
                    val = list(val)
                setattr(settings.user, attr, val)
