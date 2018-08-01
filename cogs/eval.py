# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from discord.ext import commands
from cogs import Cog
import textwrap
import traceback
import io
from contextlib import redirect_stdout
from asyncio.subprocess import PIPE

# To expose to eval
import asyncio
import discord
import re
import datetime
from collections import Counter


class Eval(Cog):
    _last_result = None

    @staticmethod
    def cleanup_code(content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.command(name='eval')
    @commands.is_owner()
    async def eval_cmd(self, ctx, *, body):
        """Evaluates a code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                fut = func()
                ret = await asyncio.wait_for(fut, 60, loop=self.bot.loop)
        except Exception as e:
            value = stdout.getvalue()
            if value:
                value = value.replace(self.bot.http.token, '{TOKEN}')
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            if value:
                value = value.replace(self.bot.http.token, '{TOKEN}')
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```'.replace(self.bot.http.token, '{TOKEN}'))

    @commands.command(name='shell')
    @commands.is_owner()
    async def eval_cmd(self, ctx, *, body):
        """Evaluates a shell script"""

        body = self.cleanup_code(body)
        process = await asyncio.create_subprocess_shell(body, stdout=PIPE, stderr=PIPE, loop=self.bot.loop)
        stdout, stderr = await process.communicate()
        stdout = stdout.decode().replace(self.bot.http.token, '{TOKEN}')
        stderr = stderr.decode().replace(self.bot.http.token, '{TOKEN}')
        returncode = process.returncode
        color = discord.Color.red() if returncode else discord.Color.green()
        embed = discord.Embed(title=f'Process returned with code {returncode}', color=color)
        if 0 < len(stdout) < 1024:
            embed.add_field(name='stdout', value=stdout)
        if 0 < len(stderr) < 1024:
            embed.add_field(name='stderr', value=stderr)
        await ctx.send(embed=embed)
        if len(stdout) >= 1024:
            buffer = io.TextIOBase()
            buffer.write(stdout)
            buffer.seek(0)
            await ctx.send('stdout', file=discord.File(buffer, stdout))
            buffer.close()
        if len(stderr) >= 1024:
            buffer = io.TextIOBase()
            buffer.write(stderr)
            buffer.seek(0)
            await ctx.send('stderr', file=discord.File(buffer, stderr))
            buffer.close()


def setup(bot):
    bot.add_cog(Eval(bot))
