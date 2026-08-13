# Use https://www.xiconeditor.com to convert to ico
import matplotlib as mp
import matplotlib.pyplot as plt
from matplotlib import patheffects as pe
import numpy as np


def make_main_icon():
    fig = plt.figure(frameon=False)
    fig.set_size_inches(1, 1)
    ax = plt.Axes(fig, [0, 0, 1, 1])
    ax.set_axis_off()
    fig.add_axes(ax)

    background = mp.patches.Rectangle([0, 0], width=1, height=1, facecolor='midnightblue',
                                       edgecolor='none', transform=ax.transAxes)
    ax.add_patch(background)

    # Linear chirp: frequency rises left-to-right, evoking the sweep
    # signals used to calibrate acoustic hardware.
    t = np.linspace(0, 1, 1000)
    f0, f1 = 2, 8
    phase = 2 * np.pi * (f0 * t + (f1 - f0) / 2 * t**2)
    y = np.sin(phase)

    spline_effect = [
        pe.Stroke(linewidth=10, foreground="white"),
        pe.Stroke(linewidth=5, foreground="cornflowerblue"),
    ]
    ax.plot(t, y, color='none', solid_capstyle='round', path_effects=spline_effect)

    ax.axis(xmin=-0.05, xmax=1.05, ymin=-1.5, ymax=1.5)

    border = mp.patches.Rectangle([0, 0], width=1, height=1, facecolor='none',
                                   edgecolor='white', linewidth=10,
                                   transform=ax.transAxes, zorder=3)
    ax.add_patch(border)
    fig.savefig('main-icon.png', transparent=False, bbox_inches='tight')


make_main_icon()
