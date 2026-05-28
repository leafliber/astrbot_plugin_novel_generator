from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Character:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    personality: str = ""
    appearance: str = ""
    background: str = ""
    notes: str = ""


@dataclass
class Relationship:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    character_a: str = ""
    character_b: str = ""
    relation_type: str = ""
    description: str = ""


@dataclass
class Event:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    timeline_position: str = ""
    description: str = ""
    involved_characters: list[str] = field(default_factory=list)


@dataclass
class Outline:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    chapter_plan: str = ""
    plot_direction: str = ""
    notes: str = ""


@dataclass
class Chapter:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    number: int = 0
    title: str = ""
    content: str = ""


@dataclass
class Novel:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    characters: list[Character] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    outlines: list[Outline] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)

    def to_dict(self) -> dict:
        import dataclasses

        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Novel:
        characters = [Character(**c) for c in data.get("characters", [])]
        relationships = [Relationship(**r) for r in data.get("relationships", [])]
        events = [Event(**e) for e in data.get("events", [])]
        outlines = [Outline(**o) for o in data.get("outlines", [])]
        chapters = [Chapter(**ch) for ch in data.get("chapters", [])]
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            name=data.get("name", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            characters=characters,
            relationships=relationships,
            events=events,
            outlines=outlines,
            chapters=chapters,
        )
