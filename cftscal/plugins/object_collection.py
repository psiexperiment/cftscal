from atom.api import Atom, Bool, Event, Value, List, observe

class ObjectNode(Atom):
    '''
    Represents a single recording or calibration in the tree hierarchy
    '''
    selected = Bool(False)
    item = Value()
    parent = Value()
    color = Value(None)

    def _observe_selected(self, event):
        if self.selected:
            self.parent.notify(self, selected=True)
        else:
            self.parent.notify(self, selected=False)


class ObjectGroup(Atom):
    '''
    Represents a group of recordings or calibration in the tree hierarchy
    '''
    selected = Bool(False)
    item = Value()
    parent = Value()
    color = Value(None)
    subitems = List(ObjectNode)

    #: Internal flag to prevent race conditions when selecting/unselecting
    #: items in tree. We have the option of checking the group (allowing
    #: us to plot the most recent recording/calibration) or unchecking the
    #: group, which will remove all recordings/calibrations under the group
    #: from the plot.
    _skip_autoselect = Bool(False)

    def __init__(self, item, parent):
        self.item = item
        self.parent = parent
        self.update_subitems()

    def notify(self, node, selected):
        self.parent.notify(node, selected)

    def update_subitems(self):
        objects = sorted(self.item.list_calibrations(), reverse=True)

        existing_nodes = {node.item.filename: node for node in self.subitems}
        new_subitems = []

        for obj in objects:
            key = obj.filename  # Use whatever attribute guarantees uniqueness
            if key in existing_nodes:
                node = existing_nodes[key]
                node.item = obj  # Update the underlying data just in case it changed
                new_subitems.append(node)
            else:
                new_subitems.append(ObjectNode(item=obj, parent=self))

        self.subitems = new_subitems

    def _observe_subitems(self, change):
        """Safely bind observers while cleaning up removed items to prevent memory leaks."""
        # Unobserve old items being removed
        if 'oldvalue' in change:
            for i in change['oldvalue']:
                i.unobserve('selected', self._check_selected)
                i.unobserve('color', self._check_color)

        # Observe new items
        if 'value' in change:
            for i in change['value']:
                i.observe('selected', self._check_selected)
                i.observe('color', self._check_color)

    def _check_selected(self, event):
        for i in self.subitems:
            if i.selected:
                self._skip_autoselect = True
                self.selected = True
                self._skip_autoselect = False
                return
        self.selected = False

    def _check_color(self, event):
        for i in self.subitems:
            if i.color is not None:
                self.color = i.color
                break
        else:
            self.color = None

    def _observe_selected(self, event):
        if self.selected:
            if not self._skip_autoselect and self.subitems:
                self.subitems[0].selected = True
        else:
            for i in self.subitems:
                i.selected = False


class ObjectCollection(Atom):
    '''
    Manages the list of recording/calibration groups
    '''
    groups = List(ObjectGroup)

    #: Manager that implements a `list_objects` method (e.g.,
    #: `starship_manager.list_objects()`) that is used to load the items that
    #: are shown in the tree.
    object_manager = Value()

    #: Managers that respond to group/node selections in the tree.
    view_managers = Value()

    updated = Event()

    def __init__(self, object_manager, view_managers):
        self.object_manager = object_manager
        self.view_managers = view_managers
        self.update_groups()

    def update_groups(self):
        objects = sorted(self.object_manager.list_objects())
        existing_groups = {group.item.name: group for group in self.groups}
        new_groups = []

        for obj in objects:
            key = obj.name  # Use whatever attribute guarantees uniqueness
            if key in existing_groups:
                group = existing_groups[key]
                group.item = obj
                group.update_subitems()
                new_groups.append(group)
            else:
                new_groups.append(ObjectGroup(obj, self))

        self.groups = new_groups
        self.updated = True

    def notify(self, node, selected):
        for manager in self.view_managers:
            result = manager.notify(node.item, selected)
            if not selected:
                node.color = None
            elif result is not None and 'color' in result:
                node.color = result['color']
