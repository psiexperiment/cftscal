'''
The user guide, shown in a web view in Home's User Guide panel.

The copy of the website bundled with cftscal (cftscal/guide, built by
tools/build_guide.py), so it works without a network; the published
website if there's no bundled copy. Just a QWebEngineView: no toolbar of
its own. Right-clicking the page gives the browser's Back, Forward and
Reload.
'''
from importlib.resources import files
import logging
log = logging.getLogger(__name__)

from atom.api import Str, Value
from enaml.core.api import d_
from enaml.widgets.api import RawWidget

#: Where the user guide is published (site_url in mkdocs.yml).
GUIDE_URL = 'https://psiexperiment.github.io/cftscal/'


def guide_url(page=''):
    '''
    Where to open a page of the user guide: in the copy bundled with
    cftscal if there is one, otherwise on the website.

    Parameters
    ----------
    page : str
        The page, as its path in docs/ without ``.md`` (e.g.
        ``'plugins/speaker'``); empty for the guide's home page.

    Returns
    -------
    url : str
        A file:// URL into cftscal/guide, or a URL under GUIDE_URL.
    '''
    from qtpy.QtCore import QUrl
    # The bundled copy links to .html files (see mkdocs-offline.yml); the
    # website to folders.
    local = files('cftscal').joinpath('guide', *f'{page or "index"}.html'.split('/'))
    if local.is_file():
        return QUrl.fromLocalFile(str(local)).toString()
    return GUIDE_URL + (f'{page}/' if page else '')


def prepare_web_engine():
    '''
    Load Qt's web engine before the Qt application is created.

    QtWebEngine refuses to start once a QApplication exists unless it was
    imported first, so cftscal.main calls this before creating one. Fails
    soft: without QtWebEngine (e.g. a build that leaves it out), the User
    Guide panel shows a link to the website instead.
    '''
    try:
        import qtpy.QtWebEngineWidgets  # noqa: F401
    except Exception:
        log.warning('QtWebEngine is not available; the User Guide panel '
                    'will link to the website instead', exc_info=True)


def _link_label(parent, url):
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QLabel
    label = QLabel(
        f'The user guide can\'t be shown here. '
        f'<a href="{url}">Open it in your web browser.</a>', parent)
    label.setOpenExternalLinks(True)
    label.setAlignment(Qt.AlignCenter)
    label.setWordWrap(True)
    return label


class GuideBrowser(RawWidget):
    '''A web view showing the user guide, starting at ``page``.'''

    #: Page of the guide the view opens on (see guide_url); empty for the
    #: guide's home page.
    page = d_(Str())

    #: Where that page is (see guide_url).
    url = d_(Str())

    view = Value()

    hug_width = 'ignore'
    hug_height = 'ignore'

    def _default_url(self):
        return guide_url(self.page)

    def create_widget(self, parent):
        try:
            from qtpy.QtCore import QUrl
            from qtpy.QtWebEngineWidgets import QWebEngineView
            self.view = QWebEngineView(parent)
        except Exception:
            # No QtWebEngine, or it was loaded too late to start (see
            # prepare_web_engine).
            log.warning('Could not create the user guide web view',
                        exc_info=True)
            self.view = _link_label(parent, GUIDE_URL)
            return self.view
        self.view.load(QUrl(self.url))
        return self.view
