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

import matplotlib.pyplot as plt
import numpy as np
import typing
import datetime


__all__ = 'set_time_xlabs', 'thin_points'


def set_time_xlabs(ax: plt.Axes, times: typing.Sequence[datetime.datetime]):
    nticks = 6
    tick_width = (times[-1] - times[0]).total_seconds() / nticks
    new_ticks = [times[0] + datetime.timedelta(seconds=tick_width * i) for i in range(nticks + 1)]
    new_labs = [tstamp.strftime('%Y-%m-%d\nT%H:%M:%S') for tstamp in new_ticks]
    ax.set_xticks(new_ticks)
    ax.set_xticklabels(new_labs, rotation=45, ha='right', ma='right')


def thin_points(cur_npoints: int, max_npoints: int):
    if cur_npoints < max_npoints:
        return np.arange(cur_npoints)
    return np.linspace(0, cur_npoints - 1, max_npoints).astype(int)
