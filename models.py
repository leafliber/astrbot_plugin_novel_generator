from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass
class Character:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    personality: str = ""
    appearance: str = ""
    background: str = ""
    notes: str = ""

    EDITABLE_FIELDS: ClassVar[set[str]] = {"name", "personality", "appearance", "background", "notes"}

    def apply_updates(self, data: dict) -> None:
        for k, v in data.items():
            if k in self.EDITABLE_FIELDS:
                setattr(self, k, v)


@dataclass
class Relationship:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    character_a: str = ""
    character_b: str = ""
    relation_type: str = ""
    description: str = ""

    EDITABLE_FIELDS: ClassVar[set[str]] = {"character_a", "character_b", "relation_type", "description"}

    def apply_updates(self, data: dict) -> None:
        for k, v in data.items():
            if k in self.EDITABLE_FIELDS:
                setattr(self, k, v)


@dataclass
class Event:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    timeline_position: str = ""
    description: str = ""
    involved_characters: list[str] = field(default_factory=list)

    EDITABLE_FIELDS: ClassVar[set[str]] = {"name", "timeline_position", "description", "involved_characters"}

    def apply_updates(self, data: dict) -> None:
        for k, v in data.items():
            if k in self.EDITABLE_FIELDS:
                setattr(self, k, v)


@dataclass
class Outline:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    chapter_plan: str = ""
    plot_direction: str = ""
    notes: str = ""
    parent_id: str = ""
    order: int = 0

    EDITABLE_FIELDS: ClassVar[set[str]] = {"title", "chapter_plan", "plot_direction", "notes", "parent_id", "order"}

    def apply_updates(self, data: dict) -> None:
        for k, v in data.items():
            if k in self.EDITABLE_FIELDS:
                setattr(self, k, v)


@dataclass
class Chapter:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    number: int = 0
    title: str = ""
    content: str = ""
    status: str = "draft"
    summary: str = ""

    EDITABLE_FIELDS: ClassVar[set[str]] = {"number", "title", "content", "status", "summary"}

    def apply_updates(self, data: dict) -> None:
        for k, v in data.items():
            if k in self.EDITABLE_FIELDS:
                setattr(self, k, v)


@dataclass
class WorldSetting:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    category: str = ""
    name: str = ""
    description: str = ""

    EDITABLE_FIELDS: ClassVar[set[str]] = {"category", "name", "description"}

    def apply_updates(self, data: dict) -> None:
        for k, v in data.items():
            if k in self.EDITABLE_FIELDS:
                setattr(self, k, v)


SCHEMA_VERSION = 1


@dataclass
class Novel:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    schema_version: int = SCHEMA_VERSION
    characters: list[Character] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    outlines: list[Outline] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    world_settings: list[WorldSetting] = field(default_factory=list)

    def resolve_character_ref(self, ref: str) -> Character | None:
        for c in self.characters:
            if c.id == ref or c.name == ref:
                return c
        return None

    def resolve_character_id(self, ref: str) -> str | None:
        c = self.resolve_character_ref(ref)
        return c.id if c else None

    def character_name_by_id(self, character_id: str) -> str:
        for c in self.characters:
            if c.id == character_id:
                return c.name
        return character_id

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Novel:
        characters = [Character(**c) for c in data.get("characters", [])]
        relationships = [Relationship(**r) for r in data.get("relationships", [])]
        events = [Event(**e) for e in data.get("events", [])]
        outlines = [Outline(**o) for o in data.get("outlines", [])]
        chapters = [Chapter(**ch) for ch in data.get("chapters", [])]
        world_settings = [WorldSetting(**w) for w in data.get("world_settings", [])]
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            name=data.get("name", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            schema_version=SCHEMA_VERSION,
            characters=characters,
            relationships=relationships,
            events=events,
            outlines=outlines,
            chapters=chapters,
            world_settings=world_settings,
        )
