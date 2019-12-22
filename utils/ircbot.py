import asyncio
from irc.client import Connection, Event
from irc.bot import SingleServerIRCBot, ServerSpec
from .botclass import LoggingMixin


class AsyncIRCBot(SingleServerIRCBot, LoggingMixin):
    def __init__(self, *args, loop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = loop or asyncio.get_event_loop()

    async def start(self):
        asyncio.create_task(self.loop.run_in_executor(None, super().start))

    def on_privmsg(self, connection: Connection, event: Event):
        self.log_debug(f'{event}')
