import asyncio
import discord
import tempfile
import traceback
from discord.ext import commands
from utils import sql
from utils.default_cog import Cog
from cogs import markov


class lower(commands.clean_content):
    async def convert(self, ctx, argument):
        arg = await super().convert(ctx, argument)
        return arg.lower()


class ModTools(Cog):
    def __local_check(self, ctx: commands.Context):
        return ctx.channel.permissions_for(ctx.author).administrator

    @commands.group(case_insensitive=True)
    async def admin(self, ctx):
        """Commands for the admin console"""

    @admin.group(case_insensitive=True)
    async def markov(self, ctx):
        """Commands to manage Markov channels"""

    @markov.command(name='add')
    async def add_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        cog: markov.Markov = self.bot.get_cog('Markov')
        if cog is None:
            return await ctx.send('Markov cog is not loaded.')
        if ch.id in cog.markov_channels:
            await ctx.send(f'Channel {ch} is already being tracked for Markov chains')
        else:
            async with ctx.typing():
                if await cog.learn_markov_from_history(ch):
                    await ctx.send(f'Successfully initialized {ch}')
                    cog.markov_channels.add(ch.id)
                else:
                    await ctx.send(f'Missing permissions to load {ch}')

    @markov.command(name='delete')
    async def del_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        cog: markov.Markov = self.bot.get_cog('Markov')
        if cog is None:
            return await ctx.send('Markov cog is not loaded.')
        if ch.id in cog.markov_channels:
            await ctx.send(f'Channel {ch} will no longer be learned')
            cog.markov_channels.discard(ch.id)
        else:
            await ctx.send(f'Channel {ch} is not being learned')

    @admin.group(case_insensitive=True)
    async def ui(self, ctx):
        """Commands to manage the bot's appearance"""

    @ui.command(name='nick')
    @commands.bot_has_permissions(change_nick=True)
    async def change_nick(self, ctx: commands.Context, *, nickname: commands.clean_content = None):
        """Change or reset the bot's nickname"""
        await ctx.me.edit(nick=nickname)
        await ctx.send('OwO')

    @ui.command(name='game')
    async def change_game(self, ctx: commands.Context, *, game: str = None):
        """Change or reset the bot's presence"""
        game = game or f'{ctx.prefix}pikahelp'
        activity = discord.Game(game)
        await self.bot.change_presence(activity=activity)
        async with self.bot.settings as settings:
            settings.user.game = game
        await ctx.send(f'I\'m now playing {game}')

    @ui.command(name='avatar')
    @commands.check(lambda ctx: len(ctx.message.attachments) == 1)
    async def change_avatar(self, ctx: commands.Context):
        with tempfile.TemporaryFile() as t:
            await ctx.message.attachments[0].save(t)
            await self.bot.user.edit(avatar=t.read())
        await ctx.send('OwO')

    @admin.group()
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

    @admin.group()
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

    @admin.group()
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
    async def call_sql(self, ctx, *, script):
        """Run arbitrary sql command"""
        try:
            await sql.call_script(script)
        except sql.sqlite3.Error:
            tb = traceback.format_exc(limit=3)
            embed = discord.Embed(color=0xff0000)
            embed.add_field(name='Traceback', value=f'```{tb}```')
            await ctx.send('The script failed with an error (check your syntax?)', embed=embed)
        else:
            await ctx.send('Script successfully executed')

    @admin.command(name='ban')
    async def ban_user(self, ctx, person: discord.Member):
        """Ban a member :datsheffy:"""
        with self.bot.settings as settings:
            settings.user.banlist.add(person.id)
        await ctx.send(f'{person.display_name} is now banned from interacting with me.')

    @admin.command(name='unban')
    async def unban_user(self, ctx, person: discord.Member):
        """Unban a member"""
        with self.bot.settings as settings:
            settings.user.banlist.discard(person.id)
        await ctx.send(f'{person.display_name} is no longer banned from interacting with me.')

    @admin.command(name='oauth')
    async def send_oauth(self, ctx: commands.Context):
        """Sends the bot's OAUTH token."""
        with self.bot.settings as settings:
            token = settings.credentials.token
        await self.bot.get_user(self.bot.owner_id).send(token)
        await ctx.message.add_reaction('☑')

    @admin.group(name='command', )
    async def admin_cmd(self, ctx: commands.Context):
        """Manage bot commands"""

    @admin_cmd.command(name='disable')
    async def disable_command(self, ctx: commands.Context, *, cmd):
        """Disable a command"""
        with self.bot.settings as settings:
            if cmd in settings.meta.disabled_commands:
                await ctx.send(f'{cmd} is already disabled')
            else:
                settings.meta.disabled_commands.add(cmd)
                await ctx.message.add_reaction('☑')

    @admin_cmd.command(name='enable')
    async def enable_command(self, ctx: commands.Context, *, cmd):
        """Enable a command"""
        with self.bot.settings as settings:
            if cmd in settings.meta.disabled_commands:
                settings.meta.disabled_commands.discard(cmd)
                await ctx.message.add_reaction('☑')
            else:
                await ctx.send(f'{cmd} is already enabled')

    @admin.group()
    async def cog(self, ctx):
        """Manage bot cogs"""

    @cog.command(name='enable')
    async def enable_cog(self, ctx, cog: lower):
        """Enable cog"""
        with self.bot.settings as settings:
            if cog not in settings.meta.disabled_cogs:
                return await ctx.send(f'Cog "{cog}" already enabled or does not exist')
            try:
                self.bot.load_extension(f'cogs.{cog}')
            except discord.ClientException:
                await ctx.send(f'Failed to load cog "{cog}"')
            else:
                await ctx.send(f'Loaded cog "{cog}"')
                settings.meta.disabled_cogs.discard(cog)

    @cog.command(name='disable')
    async def disable_cog(self, ctx, cog: lower):
        """Disable cog"""
        with self.bot.settings as settings:
            if cog in settings.user.disabled_cogs:
                return await ctx.send(f'Cog "{cog}" already disabled')
            try:
                self.bot.unload_extension(f'cogs.{cog}')
            except discord.ClientException:
                await ctx.send(f'Failed to unload cog "{cog}"')
            else:
                await ctx.send(f'Unloaded cog "{cog}"')
                settings.user.disabled_cogs.add(cog)


def setup(bot):
    bot.add_cog(ModTools(bot))
