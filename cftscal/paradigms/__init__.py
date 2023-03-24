from psi.experiment.api import ParadigmDescription


PATH = 'cftscal.paradigms.'
CORE_PATH = 'psi.paradigms.core.'


selectable_starship_mixin = {
    'manifest': PATH + 'objects.Starship',
    'required': True,
    'attrs': {'id': 'system', 'title': 'Starship', 'output_mode': 'select'}
}


ParadigmDescription(
    'pt_calibration_chirp', 'Probe tube calibration (chirp)', 'calibration', [
        {'manifest': PATH + 'pt_calibration.BasePTCalibrationManifest',},
        {'manifest': PATH + 'pt_calibration.PTChirpMixin',},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin',},
        selectable_starship_mixin,
    ],
)


ParadigmDescription(
    'pt_calibration_golay', 'Probe tube calibration (golay)', 'calibration', [
        {'manifest': PATH + 'pt_calibration.BasePTCalibrationManifest',},
        {'manifest': PATH + 'pt_calibration.PTGolayMixin',},
        selectable_starship_mixin,
    ],
)


ParadigmDescription(
    'speaker_calibration_golay', 'Speaker calibration (golay)', 'calibration', [
        {'manifest': PATH + 'speaker_calibration.BaseSpeakerCalibrationManifest',},
        {'manifest': PATH + 'calibration_mixins.GolayMixin',},
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
    'iec', 'In-ear speaker calibration (chirp)', 'ear', [
        selectable_starship_mixin,
        {'manifest': PATH + 'speaker_calibration.BaseSpeakerCalibrationManifest'},
        {'manifest': PATH + 'calibration_mixins.ChirpMixin'},
        {'manifest': PATH + 'calibration_mixins.ToneValidateMixin'},
    ]
)
