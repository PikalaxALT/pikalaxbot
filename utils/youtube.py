import asyncio
import discord
from discord.ext import commands
from concurrent.futures._base import Error
from collections import OrderedDict, deque
from datetime import timedelta

player_rxns = OrderedDict()


class VoiceCommandError(commands.CommandError):
    """This is raised when an error occurs in a voice command."""


def player_reaction(emoji):
    def decorator(coro):
        player_rxns[emoji] = coro
        return coro

    return decorator


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    def from_info(cls, filename, video, **kwargs):
        return cls(discord.FFmpegPCMAudio(filename, **kwargs), data=video)


class YouTubePlaylistHandler:
    def __init__(self, cog, *, loop=None):
        self.cog = cog
        self.loop = loop or asyncio.get_event_loop()
        self.message: discord.Message = None
        self.task: asyncio.Task = None
        self.playlist = deque()
        self.playedlist = []
        self.now_playing: YTDLSource = None
    
    def __bool__(self):
        return len(self.playlist) > 0
    
    def __len__(self):
        return len(self.playlist)
    
    def extend(self, iterable):
        self.playlist.extend(iterable)
    
    async def controls_task(self, ctx: commands.Context):
        def predicate(rxn, usr):
            return rxn.message.id == self.message.id and rxn.emoji in player_rxns

        def del_predicate(msg):
            return msg.id == self.message.id

        while True:
            tasks = [ctx.bot.wait_for(event, check=predicate) for event in ('reaction_add', 'reaction_remove')]
            tasks.append(ctx.bot.wait_for('message_delete', check=del_predicate))
            done, left = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in left:
                task.cancel()
            try:
                resp = done.pop().result()
            except IndexError:
                break
            except Error as e:
                raise VoiceCommandError from e
            if isinstance(resp, tuple) and len(resp) == 2:
                reaction, user = resp
                try:
                    await player_rxns[reaction.emoji](self, ctx)
                except Exception as exc:
                    self.cog.log_tb(ctx, exc)
            else:
                break
        self.loop.create_task(self.destroy_task())

    def player_after(self, ctx, exc):
        def done():
            ctx.cog.timeout_tasks.pop(ctx.guild.id, None)

        if exc:
            print(f'Player error: {exc}')
            return
        if self:
            self.loop.create_task(self.play_next(ctx))
        else:
            self.loop.create_task(self.destroy_task())
            self.cog.start_timeout(ctx)
            self.playedlist = []

    async def play_next(self, ctx):
        def controls_task_after():
            exc = self.task.exception()
            if exc:
                self.cog.log_tb(ctx, exc)

        if self.now_playing:
            self.playedlist.append(self.now_playing)
        self.now_playing = self.playlist.popleft()
        ctx.voice_client.play(self.now_playing, after=lambda exc: ctx.cog.player_after(ctx, exc))
        data = self.now_playing.data
        thumbnail_url = data['thumbnails'][0]['url']
        description = data['description']
        if len(description) > 250:
            description = f'{description[:250]}...'
        embed = discord.Embed(title=self.now_playing.title, description=description)
        embed.set_image(url=thumbnail_url)
        delta = timedelta(seconds=data['duration'])
        embed.set_footer(text=f'Duration: {delta}')
        if self.message:
            await self.message.edit(embed=embed)
        else:
            self.message = await ctx.send(embed=embed)
            for emoji in player_rxns:
                await self.message.add_reaction(emoji)
            if not self.task:
                self.task = self.loop.create_task(self.controls_task(ctx))
                self.task.add_done_callback(controls_task_after)

    async def destroy_task(self):
        task = self.task
        message = self.message
        self.task = None
        self.message = None
        if task is not None and not task.cancelled():
            task.cancel()
        self.playlist.clear()
        if message is not None:
            await message.delete()


@player_reaction('⏭')
async def yt_skip_video(handler: YouTubePlaylistHandler, ctx: commands.Context):
    ctx.voice_client.stop()


@player_reaction('⏮')
async def yt_prev_video(handler: YouTubePlaylistHandler, ctx: commands.Context):
    handler.playlist.appendleft(handler.now_playing)
    if handler.playedlist:
        handler.playlist.appendleft(handler.playedlist.pop())
    ctx.voice_client.stop()


@player_reaction('⏹')
async def yt_cancel_playlist(handler: YouTubePlaylistHandler, ctx: commands.Context):
    await handler.destroy_task()
    ctx.voice_client.stop()


@player_reaction('⏯')
async def yt_pause_playlist(handler: YouTubePlaylistHandler, ctx: commands.Context):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
    else:
        ctx.voice_client.pause()


@player_reaction('🔼')
async def yt_volume_up(handler: YouTubePlaylistHandler, ctx: commands.Context):
    ctx.voice_client.player.volume += 0.04


@player_reaction('🔽')
async def yt_volume_down(handler: YouTubePlaylistHandler, ctx: commands.Context):
    ctx.voice_client.player.volume -= 0.04
