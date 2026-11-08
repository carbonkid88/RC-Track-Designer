"""Undo/redo through deterministic project snapshots."""
from copy import deepcopy
from PySide6.QtGui import QUndoCommand
from .model import ConnectorRef, TrackProject


class ProjectStateCommand(QUndoCommand):
    def __init__(self, text, before, after, before_selection, after_selection,
                 before_connector, after_connector, restore):
        super().__init__(text)
        self.before, self.after = deepcopy(before), deepcopy(after)
        self.before_selection, self.after_selection = before_selection, after_selection
        self.before_connector, self.after_connector = before_connector, after_connector
        self.restore = restore
        self._first_redo = True

    def undo(self):
        self.restore(deepcopy(self.before), self.before_selection, self.before_connector)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
        else:
            self.restore(deepcopy(self.after), self.after_selection, self.after_connector)
