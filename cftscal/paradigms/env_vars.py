'''
Reads the environment variables that configure a paradigm object.

Calibration data and hardware settings are handed to an experiment
through environment variables (see, e.g., ``CalibrationSettings._run_cal``
in ``cftscal/plugins/settings.py``, which builds the environment for the
``psi`` subprocess it launches). The manifests in
``cftscal/paradigms/objects.enaml`` read those variables when the
experiment starts.

Historically, a missing variable was only logged as a warning and the
experiment carried on with whatever default the GUI happened to show.
That is fine when the experiment genuinely does not need the setting
(you cannot load a microphone calibration when the whole point of the
experiment is to *create* it), but it silently produces bad data when the
variable was simply misspelled by whoever launched the experiment.

:func:`read_env_vars` makes that distinction explicit. Each manifest
declares a ``required_vars`` list naming the settings the experiment
cannot run without. Anything named in that list but missing from the
environment raises :class:`MissingEnvironmentVariables`, and the error
message spells out the exact variable names that were expected.
'''
import logging
log = logging.getLogger(__name__)

import os


#: Standard environment variables describing an input channel. Shared by
#: everything that configures one: the `Input` and `Microphone` manifests
#: in `cftscal/paradigms/objects.enaml` (one channel, named by an
#: environment variable) and the `AllInputs` manifest in
#: `cftscal/paradigms/record.enaml` (several channels, named by
#: `CFTSCAL_INPUT_CHANNELS`).
INPUT_VARS = {
    'gain': '{prefix}_{name}_GAIN',
    'calibration': '{prefix}_{name}',
}


class MissingEnvironmentVariables(Exception):
    '''
    Raised when a required environment variable was not set.

    Attributes
    ----------
    label : str
        Name (usually the manifest ``id``) of the object that could not
        be configured.
    missing : list of tuple
        List of ``(env_var, var)`` pairs where ``env_var`` is the name of
        the environment variable that was not found and ``var`` is the
        name that setting goes by in ``required_vars``.
    blocked : list of str
        Names of required settings whose environment variables could not
        even be constructed because the variable naming the hardware
        (``name_var``) was not set.
    name_var : str
        Name of the environment variable that indicates which piece of
        hardware to use.
    '''

    def __init__(self, label, missing, blocked=None, name_var=None):
        self.label = label
        self.missing = list(missing)
        self.blocked = list(blocked) if blocked else []
        self.name_var = name_var
        super().__init__(self._format_message())

    def _format_message(self):
        # Each section is a single line. psiexperiment's error dialog
        # (`ExceptionHandler.format_exception` in psi/application) folds
        # single newlines into spaces when it reflows the message, so a
        # section that relies on line breaks to be readable would arrive
        # as a run-on line.
        lines = [f'Cannot configure "{self.label}".']
        if self.missing:
            missing = ', '.join(f'{env_var} (sets the {var})'
                                for env_var, var in self.missing)
            lines.append('The following environment variables are required, '
                         f'but were not set: {missing}.')
        if self.blocked:
            blocked = ', '.join(self.blocked)
            lines.append(
                f'The environment variable "{self.name_var}" must be set '
                f'before the following required settings can be loaded: '
                f'{blocked}.'
            )
        lines.append(
            f'If "{self.label}" does not need these settings, remove them '
            f'from the "required_vars" attribute on its manifest.'
        )
        return '\n\n'.join(lines)


def check_required_vars(label, required_vars, valid_vars):
    '''
    Check that `required_vars` only names settings that exist.

    A typo in ``required_vars`` is the same class of mistake that
    ``required_vars`` exists to catch in the environment, so it is worth
    reporting just as loudly.

    Parameters
    ----------
    label : str
        Name of the object being configured (usually the manifest
        ``id``). Only used to make the error message easier to
        understand.
    required_vars : list of str
        Settings the experiment cannot run without.
    valid_vars : list of str
        Every setting the object knows how to read.

    Raises
    ------
    ValueError
        If `required_vars` names a setting that is not in `valid_vars`.
    '''
    if unknown := [v for v in required_vars if v not in valid_vars]:
        raise ValueError(
            f'Unknown entries in required_vars for "{label}": '
            f'{", ".join(unknown)}. Valid entries are: '
            f'{", ".join(valid_vars)}.'
        )


def read_named_vars(label, name, prefix, var_templates, required_vars,
                    env=None):
    '''
    Read the environment variables configuring an already-named object.

    This is the second half of :func:`read_env_vars`, split out for
    callers that already know which piece of hardware they are
    configuring and therefore have no name to look up (e.g.,
    `initialize_all_inputs` in ``cftscal/paradigms/record.enaml``, which
    loops over the channels listed in ``CFTSCAL_INPUT_CHANNELS``).

    Unlike :func:`read_env_vars`, this function does not check
    `required_vars` for typos. The caller knows the full set of valid
    settings (which may include some this function never sees, such as
    the list of channels itself) and should pass that set to
    :func:`check_required_vars` once, rather than once per name.

    Parameters
    ----------
    label : str
        Name of the object being configured. Only used to make error
        messages easier to understand. When configuring several objects
        of the same kind, include which one this is (e.g.,
        ``'all_inputs channel microphone_1'``).
    name : str
        Name of the piece of hardware being configured, as identified in
        the IO manifest (e.g., ``'microphone_1'``). Substituted,
        uppercased, into each template.
    prefix : str
        Prefix shared by the environment variables (e.g.,
        ``'CFTSCAL_INPUT'``). Substituted into each template.
    var_templates : dict
        Maps the name of each setting (e.g., ``'gain'``) to a template
        for the environment variable that provides it. See
        :func:`read_env_vars` for the format.
    required_vars : list of str
        Settings the experiment cannot run without. Entries that are not
        keys of `var_templates` are ignored.
    env : dict, optional
        Environment to read from. Defaults to ``os.environ``. Mainly
        useful for testing.

    Returns
    -------
    values : dict
        Maps each key of `var_templates` to the value found in the
        environment or to None if that variable was not set (which can
        only happen for settings that are not listed in
        `required_vars`).

    Raises
    ------
    MissingEnvironmentVariables
        If a setting listed in `required_vars` was not found in the
        environment.

    Examples
    --------
    >>> env = {'CFTSCAL_INPUT_MICROPHONE_1_GAIN': '40'}
    >>> read_named_vars('microphone_1', 'microphone_1', 'CFTSCAL_INPUT',
    ...                 {'gain': '{prefix}_{name}_GAIN'}, ['gain'],
    ...                 env=env)
    {'gain': '40'}
    '''
    if env is None:
        env = os.environ

    values = {}
    missing = []
    for var, template in var_templates.items():
        env_var = template.format(prefix=prefix, name=name.upper())
        values[var] = env.get(env_var, None)
        if values[var] is None:
            if var in required_vars:
                missing.append((env_var, var))
            else:
                log.info('Use environment variable "%s" to set the %s for "%s".',
                         env_var, var, label)
    if missing:
        raise MissingEnvironmentVariables(label, missing)

    return values


def read_env_vars(label, name_var, var_templates, required_vars, env=None):
    '''
    Read the environment variables that configure a single object.

    All of the objects defined in ``cftscal/paradigms/objects.enaml``
    (inputs, outputs, microphones, starships, input amplifiers) follow
    the same two-step convention. One environment variable indicates
    which piece of hardware to use (e.g., ``CFTSCAL_MICROPHONE=primary``),
    and the name of every other variable is built from that value (e.g.,
    ``CFTSCAL_MICROPHONE_PRIMARY_GAIN``). This function performs both steps
    and checks that everything listed in ``required_vars`` was actually
    found.

    Parameters
    ----------
    label : str
        Name of the object being configured (usually the manifest
        ``id``). Only used to make error messages easier to understand.
    name_var : str
        Name of the environment variable indicating which piece of
        hardware to use (e.g., ``'CFTSCAL_MICROPHONE'``). In
        ``required_vars``, this setting is called ``'name'``.
    var_templates : dict
        Maps the name of each remaining setting (e.g., ``'gain'``) to a
        template for the environment variable that provides it. The
        template is formatted with two values, ``prefix`` (the value of
        `name_var`) and ``name`` (the uppercased *value* of the
        environment variable named by `name_var`). For example,
        ``{'gain': '{prefix}_{name}_GAIN'}``.
    required_vars : list of str
        Settings the experiment cannot run without. Valid entries are
        ``'name'`` plus the keys of `var_templates`. Pass an empty list
        to make every setting optional.
    env : dict, optional
        Environment to read from. Defaults to ``os.environ``. Mainly
        useful for testing.

    Returns
    -------
    values : dict
        Maps ``'name'``, plus each key of `var_templates`, to the value
        found in the environment or to None if that variable was not set
        (which can only happen for settings that are not listed in
        `required_vars`).

    Raises
    ------
    MissingEnvironmentVariables
        If a setting listed in `required_vars` was not found in the
        environment.
    ValueError
        If `required_vars` names a setting that does not exist. This
        usually means the name was misspelled.

    Examples
    --------
    >>> env = {'CFTSCAL_MICROPHONE': 'primary',
    ...        'CFTSCAL_MICROPHONE_PRIMARY_GAIN': '40'}
    >>> read_env_vars('microphone', 'CFTSCAL_MICROPHONE',
    ...               {'gain': '{prefix}_{name}_GAIN'},
    ...               ['name', 'gain'], env=env)
    {'name': 'primary', 'gain': '40'}
    '''
    if env is None:
        env = os.environ

    valid_vars = ['name'] + list(var_templates)
    check_required_vars(label, required_vars, valid_vars)

    name = env.get(name_var, None)
    if name is None:
        # Without the name we cannot even work out what the remaining
        # environment variables would have been called, so report every
        # required setting at once rather than one error per run.
        missing = [(name_var, 'name')] if 'name' in required_vars else []
        blocked = [v for v in required_vars if v != 'name']
        if missing or blocked:
            raise MissingEnvironmentVariables(label, missing, blocked, name_var)
        log.info('Environment variable "%s" not set. Not configuring "%s".',
                 name_var, label)
        return {v: None for v in valid_vars}

    values = read_named_vars(label, name, name_var, var_templates,
                             required_vars, env=env)
    return {'name': name, **values}
