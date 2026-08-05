from atom.api import Dict, Int, set_default, List, Str, Typed

from ..settings import CalibrationSettings, GeneratorSettings, InputSettings


class InputRecordingSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ())).tag(persist=True)
    generator = Typed(GeneratorSettings, ()).tag(persist=True)
    #: Session-level target folder -- one recording run now activates
    #: multiple channels at once, so there's a single shared destination
    #: rather than a per-channel one (contrast InputSettings.group_path,
    #: still used by single-selection plugins).
    group_path = Str().tag(persist=True)
    #: How many input slots are active (dropdown-controlled in the view,
    #: 1..len(available_inputs)).
    n_active_inputs = Int(1).tag(persist=True)
    #: Maps slot position (str index, "0", "1", ...) -> input_name of the
    #: real hardware channel currently assigned to that slot. Slots are
    #: independent of hardware order -- e.g. slot "0" can hold whichever
    #: channel the user picks in that slot's dropdown, not necessarily
    #: available_inputs[0]. See channel_for_slot()/assign_slot().
    #:
    #: A plain Dict (rather than a List[InputSettings]) is used here
    #: deliberately: CalibrationSettings.get_config()/set_config() only
    #: know how to persist a tagged List member if it's either empty or
    #: a list of PersistentSettings (see available_inputs above) --
    #: anything else hits an "Unknown type" ValueError. A Dict falls
    #: through to the generic scalar-style passthrough branch instead,
    #: so it round-trips as plain JSON with no extra plumbing.
    slot_channels = Dict().tag(persist=True)
    settings_filename = set_default('input-recording.json')

    def __init__(self, inputs):
        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_label=label,
                input_name=name,
            )
            settings.append(setting)
        self.available_inputs = settings
        self.generator = GeneratorSettings()
        # Default slot assignment: slot i -> the i-th real channel (the
        # same starting point as hardware order) -- overridden per-slot
        # once the user picks a different channel in that slot's
        # dropdown, or once a persisted config is loaded.
        self.slot_channels = {
            str(i): channel.input_name for i, channel in enumerate(settings)
        }

    def channel_for_slot(self, slot_index):
        '''
        Return the ``InputSettings`` currently assigned to a slot
        position (0-based).

        Falls back to the ``slot_index``-th real channel if nothing
        valid is assigned yet -- e.g. the persisted assignment names a
        channel that no longer exists on this machine.
        '''
        name = self.slot_channels.get(str(slot_index))
        for channel in self.available_inputs:
            if channel.input_name == name:
                return channel
        if 0 <= slot_index < len(self.available_inputs):
            return self.available_inputs[slot_index]
        return None

    def assign_slot(self, slot_index, channel):
        # Reassign via a fresh dict (not in-place mutation) so Atom's
        # change notification fires and reactive `<<` bindings in the
        # view pick up the new assignment.
        self.slot_channels = {
            **self.slot_channels, str(slot_index): channel.input_name,
        }

    def active_channels(self):
        return [self.channel_for_slot(i) for i in range(self.n_active_inputs)]

    def run_input_recording(self):
        active = self.active_channels()
        if not active:
            raise ValueError('No input channels are active.')
        # Two slots sharing one real channel would collide: gain and
        # calibration are properties of the physical Channel (see
        # AllInputs.initialize_all_inputs in cftscal/paradigms/
        # record.enaml), not of an individual slot, so there's no way
        # for two slots on the same channel to record independently
        # different settings -- and psi itself would separately reject
        # the resulting duplicate ContinuousInput names. The one
        # legitimate use case (e.g. saving both the calibrated and raw/
        # unity-gain version of one channel) is rare enough not to be
        # worth the added complexity of decoupling node identity from
        # channel identity for it.
        names = [c.input_name for c in active]
        if len(set(names)) != len(names):
            raise ValueError(
                'The same input channel is assigned to more than one slot.'
            )
        missing = [c.input_label for c in active if not c.sensor.name]
        if missing:
            raise ValueError(f'Select a sensor for: {", ".join(missing)}')

        pathname = self._make_path(
            'input-recording', self.group_path, self.generator.name, '{date_time}',
        )
        env = {'CFTS_INPUT_CHANNELS': ','.join(c.input_name for c in active)}
        sensors = {}
        for channel in active:
            env.update(channel.get_env_vars())
            sensors[channel.input_name] = {
                'label': channel.input_label,
                'sensor': channel.sensor.name,
            }
        metadata = {
            'generator': self.generator.name,
            'sensors': sensors,
        }
        self._run_cal(pathname, 'cftscal.paradigms.input_recording',
                      env, metadata=metadata)
