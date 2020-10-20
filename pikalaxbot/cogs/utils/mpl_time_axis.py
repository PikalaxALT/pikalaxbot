import matplotlib.pyplot as plt
import numpy as np
import typing
import datetime


__all__ = 'set_time_xlabs', 'thin_points'


def set_time_xlabs(ax: plt.Axes, times: typing.List[datetime.datetime]):
    labs = ax.get_xticklabels()
    tick_width = (times[-1] - times[0]).total_seconds() / (len(labs) - 1)
    new_labs = [(times[0] + datetime.timedelta(seconds=i * tick_width)).strftime('%Y-%m-%d\nT%H:%M:%S') for i in
                range(len(labs))]
    ax.set_xticklabels(new_labs, rotation=45, ha='right', ma='right')


def thin_points(cur_npoints, max_npoints):
    return np.linspace(0, max(cur_npoints, max_npoints), max_npoints + 1).astype(int)
