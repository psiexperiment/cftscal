'''
Exports a recording to a calibrated WAV file.

A value of 1.0 in the exported WAV file represents 1 Pascal. Arbitrary
JSON-serializable metadata (e.g. sensitivity, microphone identity,
calibration date) is embedded in a custom RIFF chunk tagged ``CFTS``,
appended after the standard ``data`` chunk. Programs that don't know
about this chunk (audio players, MATLAB's ``audioread``, etc.) skip
past it using its declared length and read the audio normally; only
code that specifically looks for the ``CFTS`` tag (e.g.
`read_calibration_wav_metadata` below) will see it.
'''
import json
from pathlib import Path
import struct

import numpy as np
from scipy.io import wavfile

_CHUNK_ID = b'CFTS'


def export_calibration(calibration, filename):
    '''
    Entry point wired to the tree view's "Export as WAV" context menu
    action (see `cftscal/plugins/fast_tree_view.enaml`,
    `_context_menu_for_leaf`).

    Parameters
    ----------
    calibration : cftscal.objects.Calibration
        The calibration the user right-clicked on. Use
        `calibration.load_recording()` for the raw voltage recording and
        `calibration.load()` for the psiaudio calibration object needed
        to convert it to Pascals.
    filename : str or Path
        Output path chosen by the user (see
        `FastTreeWidget._context_menu_for_leaf`, which prompts for this
        via a save-file dialog before calling this function).
    '''
    recording = calibration.load()
    channels = list(calibration.sensors)
    signals = [getattr(recording, ch) for ch in channels]
    fs = signals[0].fs
    for ch, sig in zip(channels, signals):
        if sig.fs != fs:
            raise ValueError(
                f'Channel "{ch}" sample rate ({sig.fs} Hz) does not match '
                f'the other channel(s) ({fs} Hz); cannot export as one '
                'interleaved WAV file.'
            )
    channel_data = [sig.get_calibration().get_level(sig[0]) for sig in signals]
    n = min(len(d) for d in channel_data)  # defensive: tolerate off-by-one length mismatches
    samples = np.stack([d[:n] for d in channel_data], axis=-1)  # (n_samples, n_channels)
    metadata = {
        'channels': channels,
        'sensors': calibration.sensors,
        'generator': calibration.generator,
        'datetime': calibration.datetime.isoformat(),
    }
    export_calibration_wav(filename, samples, fs, metadata)


def export_calibration_wav(filename, samples, fs, metadata):
    '''
    Write a calibrated recording to a WAV file.

    Parameters
    ----------
    filename : str or Path
        Output path for the WAV file.
    samples : np.ndarray
        Samples already converted to Pascals, such that a value of 1.0
        represents 1 Pa. 1D for a single channel, or 2D
        ``(n_samples, n_channels)`` for an interleaved multi-channel
        recording.
    fs : float
        Sampling rate, in Hz.
    metadata : dict
        JSON-serializable metadata to embed in the file (e.g.
        sensitivity, microphone serial number, calibration date).

    Returns
    -------
    filename : Path
        The path the file was written to (same as the `filename`
        parameter, converted to a `Path`).
    '''
    filename = Path(filename)

    # Float32 WAV: no int16 scaling/clipping to worry about, and 1.0 in
    # the file is exactly 1.0 Pa.
    wavfile.write(filename, int(fs), samples.astype(np.float32))

    payload = json.dumps(metadata).encode('utf-8')
    if len(payload) % 2:
        payload += b'\x00'  # RIFF chunks must be word-aligned
    chunk = _CHUNK_ID + struct.pack('<I', len(payload)) + payload

    with open(filename, 'r+b') as fh:
        fh.seek(0, 2)
        fh.write(chunk)
        # Patch the RIFF header's overall size (bytes 4:8) to include the
        # newly-appended chunk.
        fh.seek(4)
        riff_size = struct.unpack('<I', fh.read(4))[0]
        fh.seek(4)
        fh.write(struct.pack('<I', riff_size + len(chunk)))

    return filename


def read_calibration_wav_metadata(filename):
    '''
    Read back the JSON metadata embedded by `export_calibration_wav`.

    Parameters
    ----------
    filename : str or Path
        Path to a WAV file previously written by `export_calibration_wav`.

    Returns
    -------
    metadata : dict or None
        The embedded metadata, or None if the file has no `CFTS` chunk.
    '''
    data = Path(filename).read_bytes()
    idx = data.find(_CHUNK_ID)
    if idx == -1:
        return None
    size = struct.unpack('<I', data[idx + 4:idx + 8])[0]
    payload = data[idx + 8:idx + 8 + size]
    return json.loads(payload.rstrip(b'\x00').decode('utf-8'))
