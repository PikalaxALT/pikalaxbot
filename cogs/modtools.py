import asyncio
import discord
import tempfile
from discord.ext import commands
from utils import sql
from utils.botclass import PikalaxBOT
from utils.checks import can_learn_markov
from utils.default_cog import Cog


class ModTools(Cog):
    async def __local_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.group(pass_context=True, case_insensitive=True)
    async def admin(self, ctx):
        """Commands for the admin console"""

    @admin.group(pass_context=True, case_insensitive=True)
    async def markov(self, ctx):
        """Commands to manage Markov channels"""

    @markov.command(name='add')
    async def add_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        if ch.id in self.bot.markov_channels:
            await ctx.send(f'Channel {ch.mention} is already being tracked for Markov chains')
        else:
            async with ctx.typing():
                try:
                    async for msg in ch.history(limit=5000):
                        _ctx = await self.bot.get_context(msg)
                        if can_learn_markov(_ctx, force=True):
                            self.bot.learn_markov(_ctx)
                except discord.Forbidden:
                    await ctx.send(f'Failed to get message history from {ch.mention} (403 FORBIDDEN)')
                except AttributeError:
                    await ctx.send(f'Failed to load chain {ch.mention}')
                else:
                    await ctx.send(f'Successfully initialized {ch.mention}')
                    self.bot.markov_channels.append(ch.id)
                    self.bot.commit()

    @markov.command(name='delete')
    async def del_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        if ch.id in self.bot.markov_channels:
            await ctx.send(f'Channel {ch.mention} will no longer be learned')
            self.bot.markov_channels.remove(ch.id)
            self.bot.commit()
        else:
            await ctx.send(f'Channel {ch.mention} is not being learned')

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

    @ui.command(name='avatar')
    async def change_avatar(self, ctx: commands.Context):
        msg: discord.Message = ctx.message
        if len(msg.attachments) == 0:
            await ctx.send('No replacement avatar received')
        elif len(msg.attachments) > 1:
            await ctx.send('I don\'t know which image to use!')
        else:
            with tempfile.TemporaryFile() as t:
                await msg.attachments[0].save(t)
                await ctx.bot.user.edit(avatar=t.read())
            await ctx.send('OwO')

    @admin.group(pass_context=True)
    async def leaderboard(self, ctx):
        """Commands for manipulating the leaderboard"""

    @leaderboard.command(name='clear')
    async def clear_leaderboard(self, ctx):
        """Reset the leaderboard"""
        await sql.reset_leaderboard()
        await ctx.send('Leaderboard reset')

    @leaderboard.command(name='give')
    async def give_points(self, ctx, person: discord.Member, score: int):
        """Give points to a player"""
        if person is None:
            await ctx.send('That person does not exist')
        else:
            await sql.increment_score(person, score)
            await ctx.send(f'Gave {score:d} points to {person.name}')

    @admin.group(pass_context=True)
    async def bag(self, ctx):
        """Commands for manipulating the bag"""

    @bag.command(name='remove')
    async def remove_bag(self, ctx, msg: str):
        """Remove a phrase from the bag"""
        if await sql.remove_bag(msg):
            await ctx.send('Removed message from bag')
        else:
            await ctx.send('Cannot remove default message from bag')

    @bag.command(name='reset')
    async def reset_bag(self, ctx):
        """Reset the bag"""
        await sql.reset_bag()
        await ctx.send('Reset the bag')

    @admin.group(pass_context=True)
    async def database(self, ctx):
        """Commands for managing the database file"""

    @database.command(name='backup')
    async def backup_database(self, ctx):
        """Back up the database"""
        fname = await sql.backup_db()
        await ctx.send(f'Backed up to {fname}')

    @database.command(name='restore')
    async def restore_database(self, ctx, *, idx: int = -1):
        """Restore the database"""
        dbbak = await sql.restore_db(idx)
        if dbbak is None:
            await ctx.send('Unable to restore backup')
        else:
            await ctx.send(f'Restored backup from {dbbak}')

    @admin.command(name='sql')
    async def call_sql(self, ctx, *script):
        """Run arbitrary sql command"""
        script = ' '.join(script)
        try:
            await sql.call_script(script)
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
    async def join_channel(self, ctx, channel: discord.TextChannel):
        if channel.guild.me is None:
            await ctx.send('I\'m not on that server!')
        elif channel.id in self.bot.whitelist:
            await ctx.send(f'Already in channel {channel.mention}')
        elif not channel.permissions_for(channel.guild.me).send_messages:
            await ctx.send(f'Unable to chat in {channel.mention}')
        else:
            await channel.send('Memes are here')
            self.bot.whitelist[channel.id] = channel
            self.bot.commit()
            await ctx.send(f'Successfully joined {channel.mention}')

    @channel.command(name='leave')
    async def leave_channel(self, ctx, channel: discord.TextChannel):
        if channel.id not in self.bot.whitelist:
            await ctx.send(f'Not in channel {channel.mention}')
        else:
            self.bot.whitelist.pop(channel.id)
            self.bot.commit()
            await channel.send('Memes are leaving, cya')
            await ctx.send(f'Successfully left {channel.mention}')

    @admin.command(name='oauth')
    async def send_oauth(self, ctx: commands.Context):
        """Sends the bot's OAUTH token."""
        await ctx.author.send(self.bot._token)
        await ctx.message.add_reaction('☑')

    @admin.group(name='command', pass_context=True)
    async def admin_cmd(self, ctx: commands.Context):
        """Manage bot commands"""

    @admin_cmd.command(name='disable')
    async def disable_command(self, ctx: commands.Context, *, cmd):
        """Disable a command"""
        if await self.bot.disable_command(cmd):
            await ctx.message.add_reaction('☑')
        else:
            await ctx.send(f'{cmd} is already disabled')

    @admin_cmd.command(name='enable')
    async def enable_command(self, ctx: commands.Context, *, cmd):
        """Enable a command"""
        if await self.bot.enable_command(cmd):
            await ctx.message.add_reaction('☑')
        else:
            await ctx.send(f'{cmd} is already enabled')

    @admin.group(pass_context=True)
    async def cog(self, ctx):
        """Manage bot cogs"""

    @cog.command(name='enable')
    async def enable_cog(self, ctx, cog):
        """Enable cog"""
        if cog not in self.bot.disabled_cogs:
            return await ctx.send(f'Cog "{cog}" already enabled or does not exist')
        try:
            self.bot.load_extension(f'cogs.{cog.lower()}')
        except discord.ClientException:
            await ctx.send(f'Failed to load cog "{cog}"')
        else:
            await ctx.send(f'Loaded cog "{cog}"')
            self.bot.disabled_cogs.remove(cog.lower())

    @cog.command(name='disable')
    async def disable_cog(self, ctx, cog):
        """Disable cog"""
        if cog in self.bot.disabled_cogs:
            return await ctx.send(f'Cog "{cog}" already disabled')
        try:
            self.bot.unload_extension(f'cogs.{cog.lower()}')
        except discord.ClientException:
            await ctx.send(f'Failed to unload cog "{cog}"')
        else:
            await ctx.send(f'Unloaded cog "{cog}"')
            self.bot.disabled_cogs.append(cog.lower())


def setup(bot):
    bot.add_cog(ModTools(bot))
