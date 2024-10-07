from psi.experiment.api import ParadigmDescription


PATH = 'cftscal.paradigms.'
CORE_PATH = 'psi.paradigms.core.'


input_amplifier_mixin = {
    'manifest': PATH + 'objects.InputAmplifier',
    'required': True,
}


selectable_starship_mixin = {
    'manifest': PATH + 'objects.Starship',
    'required': True,
    'attrs': {'id': 'system', 'title': 'Starship', 'output_mode': 'select'}
}


selectable_input_mixin = {
    'manifest': PATH + 'objects.Input',
    'required': True,
    'attrs': {'id': 'selected', 'title': 'Input'},
}


selectable_microphone_mixin = {
    'manifest': PATH + 'objects.Microphone',
    'required': True,
    'attrs': {'id': 'cal', 'title': 'Microphone'},
}


selectable_speaker_mixin = {
    'manifest': PATH + 'objects.Speaker',
    'required': True,
    'attrs': {'id': 'system', 'title': 'Speaker'},
}


ParadigmDescription(
    'pt_calibration_chirp', 'Probe tube calibration (chirp)', 'calibration', [
        {'manifest': PATH + 'pt_calibration.BasePTCalibrationManifest',},
        {'manifest': PATH + 'pt_calibration.PTChirpMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        selectable_starship_mixin,
        selectable_microphone_mixin,
    ],
)


ParadigmDescription(
    'pt_calibration_golay', 'Probe tube calibration (golay)', 'calibration', [
        {'manifest': PATH + 'pt_calibration.BasePTCalibrationManifest',},
        {'manifest': PATH + 'pt_calibration.PTGolayMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        selectable_starship_mixin,
        selectable_microphone_mixin,
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
         'attrs': {'source_name': 'hw_ai', 'y_label': 'PSD (dB re 1V)'}
         },
        selectable_microphone_mixin,
    ]
)


ParadigmDescription(
    'amplifier_calibration', 'Amplifier calibration', 'calibration', [
        {'manifest': PATH + 'amplifier_calibration.AmplifierCalibrationManifest'},
        {'manifest': CORE_PATH + 'signal_mixins.SignalFFTViewManifest',
         'required': True
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


ParadigmDescription(
    'input_monitor', 'Microphone Monitor', 'calibration', [
        selectable_input_mixin,
        {'manifest': PATH + 'monitor.MonitorManifest'},
        {
            'manifest': CORE_PATH + 'signal_mixins.SignalViewManifest',
            'required': True,
            'attrs': {
                'id': 'input_signal',
                'title': 'Time',
                'time_span': 10,
                'time_delay': 0.125,
                'source_name': 'selected_input',
                'y_label': 'Signal (V)'
            },
        },
        {
            'manifest': CORE_PATH + 'signal_mixins.SignalFFTViewManifest',
            'required': True,
            'attrs': {
                'id': 'input_psd',
                'title': 'PSD',
                'fft_time_span': 0.25,
                'fft_freq_lb': 500,
                'fft_freq_ub': 50000,
                'source_name': 'selected_input',
                'y_label': 'Level (dB)',
                'apply_calibration': True,
            },
        },
    ],
)
