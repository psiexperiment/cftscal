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
