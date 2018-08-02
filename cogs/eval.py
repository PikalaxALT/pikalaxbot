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
from cogs import ClientSessionCog, has_client_session
import textwrap
import traceback
import io
from contextlib import redirect_stdout
from asyncio.subprocess import PIPE
import aiohttp

# To expose to eval
import asyncio
import discord
import re
import datetime
from collections import Counter


class Eval(ClientSessionCog):
    _last_result = None

    def __unload(self):
        task = self.bot.loop.create_task(self.cs.close())
        asyncio.wait([task], timeout=60)

    async def hastebin(self, content):
        if self.cs is None or self.cs.closed:
            self.cs = aiohttp.ClientSession(raise_for_status=True)
        res = await self.cs.post('https://hastebin.com/documents', data=content.encode('utf-8'))
        post = await res.json()
        uri = post['key']
        return f'https://hastebin.com/{uri}'

    @staticmethod
    def cleanup_code(content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    def mask_token(self, value):
        return value.replace(self.bot.http.token, '{TOKEN}')

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
                value = self.mask_token(value)
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            if value:
                value = self.mask_token(value)
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(self.mask_token(f'```py\n{value}{ret}\n```'))

    async def format_embed_value(self, embed, name, content):
        if content:
            content = self.mask_token(content)
            if len(content) >= 1000:
                try:
                    value = await self.hastebin(content)
                except aiohttp.ClientResponseError:
                    return discord.File(io.StringIO(content), f'{name}.txt')
            else:
                value = f'```{content}```'
            embed.add_field(name=name, value=value)

    @commands.command(name='shell')
    @commands.is_owner()
    async def shell_cmd(self, ctx, *, body):
        """Evaluates a shell script"""

        body = self.cleanup_code(body)
        stdout = b''
        stderr = b''

        process = await asyncio.create_subprocess_shell(body, stdout=PIPE, stderr=PIPE, loop=self.bot.loop)
        exc = None
        try:
            fut = process.communicate()
            stdout, stderr = await asyncio.wait_for(fut, 60, loop=self.bot.loop)
            await ctx.message.add_reaction('\u2705')
        except Exception as e:
            exc = e
        finally:
            returncode = process.returncode
            color = discord.Color.red() if returncode != 0 or exc else discord.Color.green()
            title = f'Process exited with status code {returncode}' if returncode is not None else 'Process timed out'
            embed = discord.Embed(title=title, color=color)
            files = [
                await self.format_embed_value(embed, 'stdout', stdout.decode()),
                await self.format_embed_value(embed, 'stderr', stderr.decode())
            ]
            if exc:
                tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                files.append(await self.format_embed_value(embed, 'traceback', tb))
            await ctx.send(embed=embed)
            for fl in files:
                if fl is not None:
                    await ctx.send(file=fl)


def setup(bot):
    bot.add_cog(Eval(bot))
