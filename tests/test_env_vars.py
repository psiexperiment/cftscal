'''
Tests for :mod:`cftscal.paradigms.env_vars` -- reading (and requiring)
the environment variables that configure a paradigm object.
'''
import os

import pytest

from cftscal.paradigms.env_vars import (
    INPUT_VARS, MissingEnvironmentVariables, check_required_vars,
    read_env_vars, read_named_vars
)


#: What `initialize_input` in cftscal/paradigms/objects.enaml passes:
#: one variable naming the channel, plus two whose names are built from
#: the value of that variable.
VAR_TEMPLATES = INPUT_VARS


def _env(**kwargs):
    env = {
        'CFTSCAL_INPUT': 'microphone_1',
        'CFTSCAL_INPUT_MICROPHONE_1_GAIN': '40',
        'CFTSCAL_INPUT_MICROPHONE_1': 'some/calibration',
    }
    env.update(kwargs)
    return env


def _read(env, required_vars=('name', 'gain', 'calibration')):
    return read_env_vars('my_input', 'CFTSCAL_INPUT', VAR_TEMPLATES,
                         list(required_vars), env=env)


class TestReadEnvVars:

    def test_all_vars_set(self):
        assert _read(_env()) == {
            'name': 'microphone_1',
            'gain': '40',
            'calibration': 'some/calibration',
        }

    def test_name_is_uppercased_in_template(self):
        # The channel name is lowercase in the IO manifest, but the
        # environment variables built from it are uppercase.
        env = {'CFTSCAL_INPUT': 'MiXeD', 'CFTSCAL_INPUT_MIXED_GAIN': '20'}
        values = _read(env, required_vars=['name', 'gain'])
        assert values['gain'] == '20'

    def test_optional_var_missing_is_none(self):
        env = _env()
        del env['CFTSCAL_INPUT_MICROPHONE_1']
        values = _read(env, required_vars=['name', 'gain'])
        assert values['calibration'] is None
        assert values['gain'] == '40'

    def test_nothing_required_and_nothing_set(self):
        assert _read({}, required_vars=[]) == {
            'name': None, 'gain': None, 'calibration': None,
        }

    def test_missing_required_var_raises(self):
        env = _env()
        del env['CFTSCAL_INPUT_MICROPHONE_1_GAIN']
        with pytest.raises(MissingEnvironmentVariables) as exc:
            _read(env)
        assert exc.value.missing == [('CFTSCAL_INPUT_MICROPHONE_1_GAIN', 'gain')]

    def test_error_names_every_missing_variable(self):
        # The whole point of the exception is to tell whoever launched
        # the experiment exactly which variables were expected.
        with pytest.raises(MissingEnvironmentVariables) as exc:
            _read({'CFTSCAL_INPUT': 'microphone_1'})
        message = str(exc.value)
        assert 'CFTSCAL_INPUT_MICROPHONE_1_GAIN' in message
        assert 'CFTSCAL_INPUT_MICROPHONE_1' in message
        assert 'my_input' in message
        assert 'required_vars' in message

    def test_missing_name_raises_when_required(self):
        with pytest.raises(MissingEnvironmentVariables) as exc:
            _read({}, required_vars=['name'])
        assert exc.value.missing == [('CFTSCAL_INPUT', 'name')]
        assert 'CFTSCAL_INPUT' in str(exc.value)

    def test_missing_name_blocks_other_required_vars(self):
        # Without the channel name we cannot even work out what the
        # remaining variables would have been called, so they are
        # reported by the name they go by in required_vars.
        with pytest.raises(MissingEnvironmentVariables) as exc:
            _read({}, required_vars=['gain', 'calibration'])
        assert exc.value.missing == []
        assert exc.value.blocked == ['gain', 'calibration']
        message = str(exc.value)
        assert 'CFTSCAL_INPUT' in message
        assert 'gain, calibration' in message

    def test_unknown_required_var_raises(self):
        # Catches a typo in required_vars itself (the same class of bug
        # that required_vars exists to catch in the environment).
        with pytest.raises(ValueError) as exc:
            _read(_env(), required_vars=['name', 'clibration'])
        assert 'clibration' in str(exc.value)
        assert 'name, gain, calibration' in str(exc.value)

    def test_defaults_to_os_environ(self, monkeypatch):
        monkeypatch.setattr(os, 'environ', _env())
        values = read_env_vars('my_input', 'CFTSCAL_INPUT', VAR_TEMPLATES,
                               ['name', 'gain', 'calibration'])
        assert values['name'] == 'microphone_1'

    def test_full_environment_variable_name_in_template(self):
        # Not every object builds the remaining variable names from the
        # first one. The starship, for example, is selected with
        # CFTSCAL_TEST_STARSHIP but configured with CFTSCAL_STARSHIP_<name>_*.
        env = {'CFTSCAL_TEST_STARSHIP': 'ss_1', 'CFTSCAL_STARSHIP_SS_1_GAIN': '40'}
        values = read_env_vars('starship', 'CFTSCAL_TEST_STARSHIP',
                               {'gain': 'CFTSCAL_STARSHIP_{name}_GAIN'},
                               ['name', 'gain'], env=env)
        assert values == {'name': 'ss_1', 'gain': '40'}


class TestReadNamedVars:
    '''
    The second half of `read_env_vars`, for callers that already know
    which piece of hardware they are configuring (see
    `initialize_all_inputs` in cftscal/paradigms/record.enaml).
    '''

    def test_all_vars_set(self):
        env = _env()
        values = read_named_vars('my_input', 'microphone_1', 'CFTSCAL_INPUT',
                                 VAR_TEMPLATES, ['gain', 'calibration'],
                                 env=env)
        # The name is already known, so it is not part of the result.
        assert values == {'gain': '40', 'calibration': 'some/calibration'}

    def test_optional_var_missing_is_none(self):
        values = read_named_vars('my_input', 'microphone_1', 'CFTSCAL_INPUT',
                                 VAR_TEMPLATES, [], env={})
        assert values == {'gain': None, 'calibration': None}

    def test_missing_required_var_raises(self):
        with pytest.raises(MissingEnvironmentVariables) as exc:
            read_named_vars('my_input', 'microphone_1', 'CFTSCAL_INPUT',
                            VAR_TEMPLATES, ['gain'], env={})
        assert exc.value.missing == [('CFTSCAL_INPUT_MICROPHONE_1_GAIN', 'gain')]

    def test_required_vars_not_in_templates_ignored(self):
        # The caller may require settings this function never sees (the
        # list of channels, for example). Checking required_vars for
        # typos is the caller's job -- see `check_required_vars`.
        values = read_named_vars('my_input', 'microphone_1', 'CFTSCAL_INPUT',
                                 VAR_TEMPLATES, ['channels'], env=_env())
        assert values['gain'] == '40'


class TestCheckRequiredVars:

    def test_valid_entries_pass(self):
        check_required_vars('my_input', ['name', 'gain'],
                            ['name', 'gain', 'calibration'])

    def test_unknown_entry_raises(self):
        with pytest.raises(ValueError) as exc:
            check_required_vars('my_input', ['name', 'clibration'],
                                ['name', 'gain', 'calibration'])
        assert 'clibration' in str(exc.value)
        assert 'my_input' in str(exc.value)
        assert 'name, gain, calibration' in str(exc.value)
