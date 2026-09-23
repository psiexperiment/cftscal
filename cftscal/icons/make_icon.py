# Generates main-icon.png and main-icon.ico. Run from anywhere:
#   python make_icon.py
#
# The frame, palette and output sizes come from psiapp.icons, shared with the
# other psi programs (pip install psiapp[icons]). Only the motif is drawn here.
from pathlib import Path

import numpy as np

from psiapp.icons import make_icon, plot_signal


HERE = Path(__file__).parent


def draw(ax):
    # Linear chirp: frequency rises left-to-right, evoking the sweep
    # signals used to calibrate acoustic hardware.
    t = np.linspace(0, 1, 100)
    f0, f1 = 1, 6
    phase = 2 * np.pi * (f0 * t + (f1 - f0) / 2 * t**2)
    plot_signal(ax, t, np.sin(phase))


if __name__ == '__main__':
    make_icon(draw, HERE / 'main-icon.png', HERE / 'main-icon.ico')
