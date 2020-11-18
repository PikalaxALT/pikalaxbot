import matplotlib.pyplot as plt
import numpy as np
import typing
import datetime


__all__ = 'set_time_xlabs', 'thin_points'


def set_time_xlabs(ax: plt.Axes, times: typing.List[datetime.datetime]):
    nticks = 6
    tick_width = (times[-1] - times[0]).total_seconds() / nticks
    new_ticks = [times[0] + datetime.timedelta(seconds=tick_width * i) for i in range(nticks + 1)]
    new_labs = [tstamp.strftime('%Y-%m-%d\nT%H:%M:%S') for tstamp in new_ticks]
    ax.set_xticks(new_ticks)
    ax.set_xticklabels(new_labs, rotation=45, ha='right', ma='right')


def thin_points(cur_npoints, max_npoints):
    if cur_npoints < max_npoints:
        return np.arange(cur_npoints)
    return np.linspace(0, cur_npoints - 1, max_npoints).astype(int)
