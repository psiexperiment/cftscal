import importlib.resources


def load_app_icon():
    '''
    Load cftscal/icons/main-icon.png as an Enaml `Icon` for window
    branding.

    Uses `importlib.resources` rather than a `__file__`-relative path so
    this keeps working if cftscal is ever installed as a zipped wheel.

    Lives in its own plain-Python module (rather than manifest.enaml,
    where it originated) so that other top-level windows -- e.g.
    workspace_view.enaml's WorkspaceSettingsView, which isn't parented
    to the main workbench window and so doesn't inherit its branding --
    can import it too without manifest.enaml and workspace_view.enaml
    importing each other.
    '''
    from enaml.icon import Icon, IconImage
    from enaml.image import Image

    data = importlib.resources.files('cftscal').joinpath(
        'icons', 'main-icon.png').read_bytes()
    return Icon(images=[IconImage(image=Image(data=data, format='png'))])
