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

import os
import pygit2
from .bot import *
from .context import *


__all__ = ('PikalaxBOT', 'MyContext')

__dirname__ = os.path.dirname(__file__) or '.'

__version__ = '0.2.1a'

if __version__.endswith(('a', 'b', 'rc')):
    try:
        repo = pygit2.Repository(os.path.join(os.path.dirname(__dirname__), '.git'))
    except pygit2.GitError:
        pass
    else:
        __version__ += f'{sum(1 for _ in repo.walk(repo.head.target))}+g{repo.head.target.hex[:7]}'
