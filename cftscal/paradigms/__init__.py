import os

from psi.experiment.api import ParadigmDescription


PATH = 'cftscal.paradigms.'
CORE_PATH = 'psi.paradigms.core.'


def active_input_channels(env_prefix='CFTS_INPUT'):
    '''
    Comma-separated CFTS_INPUT_CHANNELS -> list of channel names, one per
    active slot. cftscal's own UI (InputRecordingSettings.
    run_input_recording) rejects assigning the same real channel to more
    than one slot -- gain/calibration are properties of the physical
    Channel, not of an individual Input tap, so two slots sharing one
    channel would silently collide on those (and, one level down, psi's
    own Input.name uniqueness check would also reject the resulting
    duplicate ContinuousInput names) -- so channel names are always
    unique here in practice. Shared by record.RecordManifest/AllInputs
    (imported from here) and the input_recording ParadigmDescription
    below, so all consumers always agree on which channels are active
    for a given run.
    '''
    raw = os.environ.get(f'{env_prefix}_CHANNELS', '')
    return [name for name in raw.split(',') if name]


def _input_plot_sources(channels, colors=('k', 'r', 'b', 'g', 'm', 'c')):
    return {
        name: {'color': colors[i % len(colors)]}
        for i, name in enumerate(channels)
    }


all_inputs_mixin = {
    'manifest': PATH + 'record.AllInputs',
    'required': True,
    # Defaults are right here: InputRecordingSettings.
    # run_input_recording() sets CFTS_INPUT_CHANNELS plus a gain and a
    # calibration for every channel it launches with (it refuses to
    # launch at all until every active channel has a sensor), so all
    # three are required.
}


input_amplifier_mixin = {
    'manifest': PATH + 'objects.InputAmplifier',
    'required': True,
}


# Every objects.* manifest below reads its configuration from
# environment variables and, by default, raises an error naming the
# variables it expected if any are missing (see
# `cftscal/paradigms/objects.enaml`). A calibration paradigm is usually
# the thing that *creates* one of those calibrations, so it has none to
# load yet -- hence the `required_vars` overrides here. Each one must
# match what the corresponding plugin actually puts in the environment
# (the `include_cal` arguments to `get_env_vars` in
# `cftscal/plugins/*/settings.py`).


selectable_starship_mixin = {
    'manifest': PATH + 'objects.Starship',
    'required': True,
    'attrs': {'id': 'system', 'title': 'Starship', 'output_mode': 'select'}
}


# Used by the probe-tube calibration paradigms, which create the
# starship's probe-tube microphone calibration (see
# `StarshipCalibrationSettings.run_cal_*`, which passes
# `include_cal=False`).
uncalibrated_starship_mixin = {
    **selectable_starship_mixin,
    'attrs': {
        **selectable_starship_mixin['attrs'],
        'required_vars': ['name', 'gain'],
    },
}


selectable_input_mixin = {
    'manifest': PATH + 'objects.Input',
    'required': True,
    # The IR sensor is just a photodetector. There's no calibration to
    # load for it (see `IRSensorSettings.run_recording`).
    'attrs': {
        'id': 'selected_input',
        'title': 'Input',
        'required_vars': ['name', 'gain'],
    },
}


selectable_microphone_mixin = {
    'manifest': PATH + 'objects.Microphone',
    'required': True,
    'attrs': {
        'id': 'cal_microphone',
        'title': 'Microphone',
        'microphone_type': 'measurement_microphone'
    },
}


# Used by the pistonphone paradigm, which creates the measurement
# microphone's calibration (see `MicrophoneCalibrationSettings.
# run_calibration`, which passes `include_cal=False`).
uncalibrated_microphone_mixin = {
    **selectable_microphone_mixin,
    'attrs': {
        **selectable_microphone_mixin['attrs'],
        'required_vars': ['name', 'gain'],
    },
}


selectable_output_mixin = {
    'manifest': PATH + 'objects.Output',
    'required': True,
    # As with `selectable_input_mixin`, the IR sensor's output (the IR
    # LED) has no calibration.
    'attrs': {
        'id': 'selected_output',
        'title': 'Output',
        'required_vars': ['name'],
    },
}


selectable_speaker_mixin = {
    'manifest': PATH + 'objects.Speaker',
    'required': True,
    # The speaker is only used as a sound source that the microphones can
    # both record, so its calibration is never loaded for these paradigms
    # (see `SpeakerCalibrationSettings.run_cal` and
    # `MicrophoneComparisonSettings.run_calibration`).
    'attrs': {
        'id': 'system',
        'title': 'Speaker',
        'required_vars': ['name'],
    },
}


ParadigmDescription(
    # Calibrates probe-tube microphone in starship.
    'pt_calibration_chirp', 'Probe tube calibration (chirp)', 'calibration', [
        {'manifest': PATH + 'pt_calibration.BasePTCalibrationManifest',},
        {'manifest': PATH + 'pt_calibration.PTChirpMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        uncalibrated_starship_mixin,
        selectable_microphone_mixin,
    ],
)


ParadigmDescription(
    # Calibrates probe-tube microphone in starship.
    'pt_calibration_golay', 'Probe tube calibration (golay)', 'calibration', [
        {'manifest': PATH + 'pt_calibration.BasePTCalibrationManifest',},
        {'manifest': PATH + 'pt_calibration.PTGolayMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        uncalibrated_starship_mixin,
        selectable_microphone_mixin,
    ],
)


ParadigmDescription(
    'mic_calibration_chirp', 'Generic microphone calibration (chirp)', 'calibration', [
        {'manifest': PATH + 'generic_mic_calibration.GenericMicCalibrationManifest',},
        {'manifest': PATH + 'generic_mic_calibration.GenericMicChirpMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        selectable_speaker_mixin,
        {
            'manifest': PATH + 'objects.Microphone',
            'required': True,
            'attrs': {
                'id': 'measurement_microphone',
                'title': 'Microphone',
                'microphone_type': 'measurement_microphone'
            },
        },
        {
            'manifest': PATH + 'objects.Microphone',
            'required': True,
            'attrs': {
                'id': 'generic_microphone',
                'title': 'Generic Microphone',
                'microphone_type': 'generic_microphone',
                'env_prefix': 'CFTS_GENERIC_MICROPHONE',
                # This is the microphone being calibrated, so there is
                # no calibration to load for it yet.
                'required_vars': ['name', 'gain'],
            },
        },
    ],
)


ParadigmDescription(
    # Calibrates probe-tube microphone in starship.
    'mic_calibration_golay', 'Generic microphone calibration (golay)', 'calibration', [
        {'manifest': PATH + 'generic_mic_calibration.GenericMicCalibrationManifest',},
        {'manifest': PATH + 'generic_mic_calibration.GenericMicGolayMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        selectable_speaker_mixin,
        {
            'manifest': PATH + 'objects.Microphone',
            'required': True,
            'attrs': {
                'id': 'measurement_microphone',
                'title': 'Microphone',
                'microphone_type': 'measurement_microphone'
            },
        },
        {
            'manifest': PATH + 'objects.Microphone',
            'required': True,
            'attrs': {
                'id': 'generic_microphone',
                'title': 'Generic Microphone',
                'microphone_type': 'generic_microphone',
                'env_prefix': 'CFTS_GENERIC_MICROPHONE',
                # This is the microphone being calibrated, so there is
                # no calibration to load for it yet.
                'required_vars': ['name', 'gain'],
            },
        },
    ],
)


ParadigmDescription(
    'speaker_calibration_golay', 'Speaker calibration (golay)', 'calibration', [
        {'manifest': PATH + 'speaker_calibration.BaseSpeakerCalibrationManifest',},
        {'manifest': PATH + 'calibration_mixins.GolayMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        selectable_microphone_mixin,
        selectable_speaker_mixin,
    ],
)


ParadigmDescription(
    'speaker_calibration_chirp', 'Speaker calibration (chirp)', 'calibration', [
        {'manifest': PATH + 'speaker_calibration.BaseSpeakerCalibrationManifest',},
        {'manifest': PATH + 'calibration_mixins.ChirpMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',
         'attrs': {'show_toolbar_button': False}
         },
        selectable_microphone_mixin,
        selectable_speaker_mixin,
    ],
)


ParadigmDescription(
    'pistonphone_calibration', 'Pistonphone calibration', 'calibration', [
        {'manifest': PATH + 'pistonphone_calibration.PistonphoneCalibrationManifest'},
        {'manifest': CORE_PATH + 'signal_mixins.SignalViewManifest',
         'required': True,
         'attrs': {'source_name': 'hw_ai', 'time_span': 8, 'y_label': 'PSD (dB re 1V)'},
         },
        {'manifest': CORE_PATH + 'signal_mixins.SignalFFTViewManifest',
         'required': True,
         'attrs': {'source_name': 'hw_ai', 'y_label': 'PSD (dB re 1V)', 'axis_scale': 'octave'}
         },
        uncalibrated_microphone_mixin,
    ]
)


ParadigmDescription(
    'amplifier_calibration', 'Amplifier calibration', 'calibration', [
        {'manifest': PATH + 'amplifier_calibration.AmplifierCalibrationManifest'},
        {'manifest': CORE_PATH + 'signal_mixins.SignalFFTViewManifest',
         'required': True,
         'attrs': {'axis_scale': 'octave'},
         },
        {'manifest': CORE_PATH + 'signal_mixins.SignalViewManifest',
         'required': True
         },
    ]
)


ParadigmDescription(
    'iec', 'In-ear speaker calibration (chirp)', 'calibration', [
        selectable_starship_mixin,
        {
            'manifest': PATH + 'speaker_calibration.BaseSpeakerCalibrationManifest',
            'attrs': {'mic_source_name': 'system_microphone'},
        },
        {'manifest': PATH + 'calibration_mixins.ChirpMixin'},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin'},
    ]
)


ParadigmDescription(
    'input_amplifier_calibration', 'Input Amplifier calibration', 'calibration', [
        input_amplifier_mixin,

        {'manifest': PATH + 'input_amplifier_calibration.InputAmplifierCalibrationManifest'},
        {
            'manifest': CORE_PATH + 'signal_mixins.SignalViewManifest',
            'required': True,
            'attrs': {
                'id': 'input_amplifier_filtered_view',
                'title': 'Input amplifier display',
                'time_span': 2,
                'time_delay': 0.125,
                'source_name': 'input_amplifier_filtered',
                'y_label': 'EEG (V)'
            },
        },
    ],
)


_input_recording_sources = _input_plot_sources(active_input_channels())

ParadigmDescription(
    'input_recording', 'Input Recording', 'calibration', [
        all_inputs_mixin,
        {'manifest': PATH + 'record.RecordManifest'},
        {
            'manifest': CORE_PATH + 'signal_mixins.MultiSignalViewManifest',
            'required': True,
            'attrs': {
                'id': 'input_signal',
                'title': 'Time',
                'time_span': 10,
                'time_delay': 0.125,
                'y_label': 'Signal (V)',
                'sources': _input_recording_sources,
            },
        },
        {
            'manifest': CORE_PATH + 'signal_mixins.MultiSignalFFTViewManifest',
            'required': True,
            'attrs': {
                'id': 'input_psd',
                'title': 'PSD',
                'fft_time_span': 0.25,
                'fft_freq_lb': 500,
                'fft_freq_ub': 50000,
                'axis_scale': 'octave',
                'y_label': 'Level (dB)',
                'apply_calibration': True,
                'sources': _input_recording_sources,
            },
        },
    ],
)


ParadigmDescription(
    'ir_sensor', 'IR Sensor', 'calibration', [
        {'manifest': PATH + 'ir_sensor.IRSensorManifest'},
        selectable_input_mixin,
        selectable_output_mixin,
        {
            'manifest': PATH + 'ir_sensor.StrobedIR',
            'required': 'True',
            'attrs': {
                'output_names': ['selected_output'],
                'input_names': ['selected_input'],
            },
        },
        {
            'manifest': CORE_PATH + 'signal_mixins.SignalViewManifest',
            'required': True,
            'attrs': {
                'id': 'input_signal',
                'title': 'Time',
                'time_span': 2,
                'time_delay': 0,
                'source_name': 'selected_input_raw',
                'y_label': 'Signal (V)'
            },
        },
        {
            'manifest': CORE_PATH + 'signal_mixins.SignalFFTViewManifest',
            'required': True,
            'attrs': {
                'id': 'input_psd',
                'title': 'PSD',
                'fft_time_span': 1,
                'fft_freq_lb': 500,
                'fft_freq_ub': 50000,
                'source_name': 'selected_input',
                'y_label': 'Level (dB)',
            },
        },
    ],
)
