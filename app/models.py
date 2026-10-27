"""Shared, UI-independent data types for the context-menu manager."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Category = Literal['desktop', 'folders', 'files', 'drives']
EntryKind = Literal['command', 'extension']

@dataclass(frozen=True, slots=True)
class MenuEntry:
    category: Category
    category_label: str
    root_name: str
    relative_key: str
    name: str
    source: str
    kind: EntryKind
    command: str = ''
    icon_location: str = ''
    clsid: str = ''
    disabled_reason: str = ''
    is_protected: bool = False
    can_edit: bool = False
    application: str = ''

    @property
    def id(self) -> str:
        return f'{self.root_name}\\{self.relative_key}'.lower()

    @property
    def registry_path(self) -> str:
        return f'{self.root_name}\\{self.relative_key}'

    @property
    def is_disabled(self) -> bool:
        return bool(self.disabled_reason)

    @property
    def status(self) -> str:
        return 'מוסתר' if self.is_disabled else 'פעיל'
