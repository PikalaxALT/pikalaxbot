import asyncio
import discord
from discord.ext import commands
from utils.markov import Chain
from utils.checks import ctx_is_owner
from utils import sql
from utils.botclass import PikalaxBOT


class ModTools():
    def __init__(self, bot: PikalaxBOT):
        self.bot = bot

    @commands.group(pass_context=True, case_insensitive=True)
    @commands.check(ctx_is_owner)
    async def admin(self, ctx):
        """Commands for the admin console"""

    @admin.group(pass_context=True, case_insensitive=True)
    async def markov(self, ctx):
        """Commands to manage Markov channels"""

    @markov.command(name='add')
    async def add_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        if ch.id in self.bot.chains:
            await ctx.send(f'Channel {ch.mention} is already being tracked for Markov chains')
        else:
            async with ctx.typing():
                self.bot.chains[ch.id] = Chain(store_lowercase=True)
                try:
                    async for msg in ch.history(limit=5000):
                        self.bot.learn_markov(msg, force=True)
                except discord.Forbidden:
                    self.bot.chains.pop(ch.id)
                    await ctx.send(f'Failed to get message history from {ch.mention} (403 FORBIDDEN)')
                except AttributeError:
                    self.bot.chains.pop(ch.id)
                    await ctx.send(f'Failed to load chain {ch.mention}')
                else:
                    await ctx.send(f'Successfully initialized {ch.mention}')
                    self.bot.markov_channels.append(ch.id)
                    self.bot.commit()

    @markov.command(name='delete')
    async def del_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        if ch.id in self.bot.chains:
            self.bot.chains.pop(ch.id)
            await ctx.send(f'Channel {ch.mention} has been forgotten')
            self.bot.markov_channels.remove(ch.id)
            self.bot.commit()
        else:
            await ctx.send(f'Channel {ch.mention} is already forgotten')

    @admin.group(pass_context=True, case_insensitive=True)
    async def ui(self, ctx):
        """Commands to manage the bot's appearance"""

    @ui.command(name='nick')
    async def change_nick(self, ctx: commands.Context, *, nickname: str = None):
        """Change or reset the bot's nickname"""
        try:
            await ctx.me.edit(nick=nickname)
        except discord.Forbidden:
            await ctx.send('Unable to change my own nickname (FORBIDDEN)')
        else:
            await ctx.send('OwO')

    @ui.command(name='game')
    async def change_game(self, ctx: commands.Context, *, game: str = None):
        """Change or reset the bot's presence"""
        game = game or f'{ctx.prefix}pikahelp'
        activity = discord.Game(game)
        try:
            await self.bot.change_presence(activity=activity)
        except discord.Forbidden:
            await ctx.send('Unable to update my presence (FORBIDDEN)')
        else:
            self.bot.game = game
            self.bot.commit()
            await ctx.send(f'I\'m now playing {game}')

    @admin.group(pass_context=True)
    async def leaderboard(self, ctx):
        """Commands for manipulating the leaderboard"""

    @leaderboard.command(name='clear')
    async def clear_leaderboard(self, ctx):
        """Reset the leaderboard"""
        sql.reset_leaderboard()
        await ctx.send('Leaderboard reset')

    @leaderboard.command(name='give')
    async def give_points(self, ctx, person: discord.Member, score: int):
        """Give points to a player"""
        if person is None:
            await ctx.send('That person does not exist')
        else:
            sql.increment_score(person, score)
            await ctx.send(f'Gave {score:d} points to {person.name}')

    @admin.group(pass_context=True)
    async def bag(self, ctx):
        """Commands for manipulating the bag"""

    @bag.command(name='remove')
    async def remove_bag(self, ctx, msg: str):
        """Remove a phrase from the bag"""
        if sql.remove_bag(msg):
            await ctx.send('Removed message from bag')
        else:
            await ctx.send('Cannot remove default message from bag')

    @bag.command(name='reset')
    async def reset_bag(self, ctx):
        """Reset the bag"""
        sql.reset_bag()
        await ctx.send('Reset the bag')

    @admin.group(pass_context=True)
    async def database(self, ctx):
        """Commands for managing the database file"""

    @database.command(name='backup')
    async def backup_database(self, ctx):
        """Back up the database"""
        await ctx.send(f'Backed up to {sql.backup_db()}')

    @database.command(name='restore')
    async def restore_database(self, ctx, *, idx: int = -1):
        """Restore the database"""
        dbbak = sql.restore_db(idx)
        if dbbak is None:
            await ctx.send('Unable to restore backup')
        else:
            await ctx.send(f'Restored backup from {dbbak}')

    @admin.command(name='sql')
    async def call_sql(self, ctx, *script):
        """Run arbitrary sql command"""
        script = ' '.join(script)
        try:
            sql.call_script(script)
        except sql.sqlite3.Error:
            await ctx.send('The script failed with an error (check your syntax?)')
        else:
            await ctx.send('Script successfully executed')

    @admin.command(name='ban')
    async def ban_user(self, ctx, person: discord.Member):
        """Ban a member :datsheffy:"""
        self.bot.ban(person)
        await ctx.send(f'{person.display_name} is now banned from interacting with me.')

    @admin.command(name='unban')
    async def unban_user(self, ctx, person: discord.Member):
        """Unban a member"""
        self.bot.unban(person)
        await ctx.send(f'{person.display_name} is no longer banned from interacting with me.')

    @admin.group(pass_context=True)
    async def channel(self, ctx):
        """Manage the bot's presence in channels/servers"""

    @channel.command(name='join')
    async def join_channel(self, ctx, chid: int):
        """Join a text channel"""
        channel: discord.TextChannel = self.bot.get_channel(id=chid)
        guild: discord.Guild = channel.guild
        me: discord.Member = guild.get_member(self.bot.user.id)
        if channel is None:
            await ctx.send('Unable to find channel')
        elif channel.id in self.bot.whitelist:
            await ctx.send(f'Already in channel {channel.mention}')
        elif not channel.permissions_for(me).send_messages:
            await ctx.send(f'Unable to chat in {channel.mention}')
        else:
            await channel.send('Memes are here')
            self.bot.whitelist.append(channel.id)
            self.bot.commit()
            await ctx.send(f'Successfully joined {channel.mention}')

    @channel.command(name='leave')
    async def leave_channel(self, ctx, chid: int):
        """Leave a text channel"""
        channel = self.bot.get_channel(id=chid)
        guild: discord.Guild = channel.guild
        me: discord.Member = guild.get_member(self.bot.user.id)
        if channel is None:
            await ctx.send('Unable to find channel')
        elif channel.id not in self.bot.whitelist:
            await ctx.send(f'Not in channel {channel.mention}')
        else:
            self.bot.whitelist.remove(channel.id)
            self.bot.commit()
            await channel.send('Memes are leaving, cya')
            await ctx.send(f'Successfully left {channel.mention}')


def setup(bot):
    bot.add_cog(ModTools(bot))
