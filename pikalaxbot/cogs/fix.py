# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
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

import re
import time
import discord
from discord.ext import commands
from . import *
import typing
from sqlalchemy import Column, TEXT, select, delete, bindparam
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import insert


class Fix(BaseTable):
    _initial_bot_owners = {
        'pika': 'PikalaxALT',
        'groudon': 'chfoo',
        'yay': 'azum and tustin',
        'updater': 'tustin',
        'starmie': 'Danny',
        'danny': 'Danny',
        'meme': 'Jet'
    }
    _initial_bot_names = {
        'yay': 'xfix\'s bot'
    }

    name = Column(TEXT, primary_key=True)
    owner = Column(TEXT, nullable=False)
    altname = Column(TEXT)

    @classmethod
    async def init(cls, conn: AsyncConnection):
        statement = insert(cls).values(
            name=bindparam('name'),
            owner=bindparam('owner'),
            altname=bindparam('altname')
        ).on_conflict_do_nothing(index_elements=['name'])
        await conn.execute(statement, [{
            'name': key,
            'owner': value,
            'altname': cls._initial_bot_names.get(key)
        } for key, value in cls._initial_bot_owners.items()])

    @classmethod
    async def fetchall(cls, conn: AsyncConnection):
        statement = select(cls)
        result = await conn.execute(statement)
        return result.all()

    @classmethod
    async def set_alias(cls, conn: AsyncConnection, name: str, owner: str, altname: str = None):
        statement = insert(cls).values(
            name=name,
            owner=owner,
            altname=altname
        )
        upsert = statement.on_conflict_do_update(
            index_elements=['name'],
            set_={
                'owner': statement.excluded.owner,
                'altname': statement.excluded.altname
            }
        )
        await conn.execute(upsert)

    @classmethod
    async def remove_alias(cls, conn: AsyncConnection, name: str):
        statement = delete(cls).where(cls.name == name)
        await conn.execute(statement)


class FixCog(BaseCog, name='Fix'):
    """Use these commands to yell at bot developers."""

    initial_bot_owners = {
        'pika': 'PikalaxALT',
        'groudon': 'chfoo',
        'yay': 'azum and tustin',
        'updater': 'tustin',
        'starmie': 'Danny',
        'danny': 'Danny',
        'meme': 'Jet'
    }
    initial_bot_names = {
        'yay': 'xfix\'s bot'
    }

    def __init__(self, bot):
        super().__init__(bot)
        self.bot_owners: dict[str, str] = {}
        self.bot_names: dict[str, str] = {}

    async def init_db(self, sql):
        await Fix.create(sql)
        await Fix.init(sql)
        for name, owner, altname in await Fix.fetchall(sql):
            self.bot_owners[name] = owner
            if altname:
                self.bot_names[name] = altname
        self.fix.update(aliases=[f'fix{name}' for name in self.bot_owners])

    @staticmethod
    def get_fix_alias(ctx: MyContext) -> typing.Optional[str]:
        match = re.match(r'fix(\w*)', ctx.invoked_with or '')
        return match and match.group(1)

    @commands.group(invoke_without_command=True)
    async def fix(self, ctx: MyContext):
        """`{ctx.prefix}fix<botname>` - Nag the bot's owner to fix their bot"""
        alias = self.get_fix_alias(ctx)
        owner = self.bot_owners.get(alias, 'already')
        botname = self.bot_names.get(alias, 'your bot')
        await ctx.send(f'"Fix {botname}, {owner}!" - PikalaxALT {time.gmtime().tm_year:d}')

    @fix.command()
    async def add(self, ctx: MyContext, key: str.lower, owner: str, altname: str = None):
        """Add a bot to my database"""
        if key not in self.bot_owners:
            self.bot_owners[key] = owner
            if altname:
                self.bot_owners[key] = altname
            elif key in self.bot_names:
                del self.bot_names[key]
            async with self.bot.sql as sql:
                await Fix.set_alias(sql, key, owner, altname)
                self.fix.update(aliases=set(self.fix.aliases) | {f'fix{key}'})
            await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')
        else:
            await ctx.message.add_reaction('\N{CROSS MARK}')

    @fix.command(name='del')
    async def delete_key(self, ctx: MyContext, key: str.lower):
        """Remove a bot from my database"""
        if key in self.bot_owners:
            del self.bot_owners[key]
            if key in self.bot_names:
                del self.bot_names[key]
            async with self.bot.sql as sql:
                await Fix.remove_alias(sql, key)
                self.fix.update(aliases=set(self.fix.aliases) - {f'fix{key}'})
            await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')
        else:
            await ctx.message.add_reaction('\N{CROSS MARK}')


def setup(bot: PikalaxBOT):
    bot.add_cog(FixCog(bot))


def teardown(bot: PikalaxBOT):
    Fix.unlink()
