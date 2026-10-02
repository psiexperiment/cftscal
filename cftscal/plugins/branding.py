import importlib.resources


def _icon_frames():
    '''
    Every size in cftscal/icons/main-icon.ico (16 to 256 px), as PNG bytes.

    The .ico rather than main-icon.png (256 px only): with just one large
    image, Windows scales it down for the title bar and taskbar, which can
    look blurry. Read from the package data with `importlib.resources`
    rather than a `__file__`-relative path, so this keeps working if
    cftscal is ever installed as a zipped wheel.
    '''
    from qtpy.QtCore import QBuffer, QByteArray, QIODevice

    from qtpy.QtGui import QImageReader

    data = importlib.resources.files('cftscal').joinpath(
        'icons', 'main-icon.ico').read_bytes()
    source = QBuffer()
    source.setData(QByteArray(data))
    source.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(source, b'ico')
    frames = []
    for i in range(reader.imageCount()):
        reader.jumpToImage(i)
        image = reader.read()
        if image.isNull():
            continue
        png = QBuffer()
        png.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(png, 'PNG')
        frames.append(bytes(png.data()))
    return frames


def load_app_icon():
    '''
    The cftscal icon, at every size in main-icon.ico, as an Enaml `Icon`
    for window branding.

    Lives in its own plain-Python module (rather than manifest.enaml,
    where it originated) so that other top-level windows -- e.g.
    workspace_view.enaml's WorkspaceSettingsView, which isn't parented
    to the main workbench window and so doesn't inherit its branding --
    can import it too without manifest.enaml and workspace_view.enaml
    importing each other.
    '''
    from enaml.icon import Icon, IconImage
    from enaml.image import Image

    return Icon(images=[IconImage(image=Image(data=frame, format='png'))
                        for frame in _icon_frames()])


def load_app_qicon():
    '''
    The same icon as a QIcon, for QApplication.setWindowIcon. Needs a
    QApplication to exist (it builds QPixmaps).
    '''
    from qtpy.QtGui import QIcon, QPixmap

    icon = QIcon()
    for frame in _icon_frames():
        pixmap = QPixmap()
        pixmap.loadFromData(frame, 'PNG')
        icon.addPixmap(pixmap)
    return icon


#: Color the workspace icons are drawn in: the navy of the cftscal logo.
WORKSPACE_ICON_COLOR = '#1a1a6e'


def load_workspace_icon(name, size=96):
    '''
    One of the workspace icons in cftscal/icons/workspaces, as an Enaml
    `Icon` -- the icons the user guide's Plugins page shows for each
    workspace (Material Design Icons; see the LICENSE file there).

    Parameters
    ----------
    name : str
        The icon's file name without ``.svg``, e.g. ``'microphone'``.
    size : int
        Pixels to draw it at. Drawn from the SVG at this size rather than
        scaled up from the SVG's nominal 24 px, so it stays sharp.

    Returns
    -------
    icon : enaml.icon.Icon or None
        None if there's no such icon.
    '''
    from enaml.icon import Icon, IconImage
    from enaml.image import Image
    from qtpy.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from qtpy.QtGui import QImage, QPainter
    from qtpy.QtSvg import QSvgRenderer

    path = importlib.resources.files('cftscal').joinpath(
        'icons', 'workspaces', f'{name}.svg')
    if not path.is_file():
        return None
    svg = path.read_text(encoding='utf-8')
    # The icons are single-color paths with no fill of their own, so a
    # fill on the root element colors the whole icon.
    svg = svg.replace('<svg ', f'<svg fill="{WORKSPACE_ICON_COLOR}" ', 1)
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    png = QBuffer()
    png.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(png, 'PNG')
    return Icon(images=[IconImage(image=Image(data=bytes(png.data()), format='png'))])
