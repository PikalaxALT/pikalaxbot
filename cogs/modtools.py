import asyncio
import discord
from discord.ext import commands
from utils.markov import Chain
from utils.config_io import Settings
from utils.checks import ctx_is_owner


class ModTools():
    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True)
    @commands.check(ctx_is_owner)
    async def admin(self, ctx):
        pass

    @admin.group(pass_context=True)
    async def markov(self, ctx):
        pass

    @markov.command(name='add')
    async def add_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        if ch.id in self.bot.chains:
            await ctx.send(f'Channel {ch.mention} is already being tracked for Markov chains')
        else:
            async with ctx.typing():
                self.bot.chains[ch.id] = Chain(store_lowercase=True)
                try:
                    async for msg in ch.history(limit=5000):
                        self.bot.learn_markov(msg, force=True)
                    await ctx.send(f'Successfully initialized {ch.mention}')
                    with Settings() as settings:
                        settings.add_markov_channel(ch.id)
                    self.bot.markov_channels.append(ch.id)
                except discord.Forbidden:
                    self.bot.chains.pop(ch.id)
                    await ctx.send(f'Failed to get message history from {ch.mention} (403 FORBIDDEN)')
                except AttributeError:
                    self.bot.chains.pop(ch.id)
                    await ctx.send(f'Failed to load chain {ch.mention}')

    @markov.command(name='delete')
    async def del_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        if ch.id in self.bot.chains:
            self.bot.chains.pop(ch.id)
            await ctx.send(f'Channel {ch.mention} has been forgotten')
            with Settings() as settings:
                settings.del_markov_channel(ch.id)
            self.bot.markov_channels.remove(ch.id)
        else:
            await ctx.send(f'Channel {ch.mention} is already forgotten')

    @admin.group(pass_context=True)
    async def ui(self, ctx):
        pass

    @ui.command(name='nick')
    async def change_nick(self, ctx: commands.Context, *, nickname: str = None):
        try:
            await ctx.me.edit(nick=nickname)
        except discord.Forbidden:
            await ctx.send('Unable to change my own nickname (FORBIDDEN)')
        else:
            await ctx.send('OwO')

    @ui.command(name='game')
    async def change_game(self, ctx: commands.Context, *, game: str = None):
        game = game or f'{ctx.prefix}pikahelp'
        activity=discord.Game(game)
        try:
            await self.bot.change_presence(activity=activity)
        except discord.Forbidden:
            await ctx.send('Unable to update my presence (FORBIDDEN)')
        else:
            with Settings() as settings:
                settings.set('user', 'game', game)


def setup(bot):
    bot.add_cog(ModTools(bot))
