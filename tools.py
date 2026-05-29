from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from pydantic import Field as PydanticField

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from .models import Character, Chapter, Event, Outline, Relationship
from .storage import NovelStorage


@dataclass
class CharacterTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_character"
    description: str = "管理小说中的角色画像。支持创建、查询、修改、删除角色信息，包括姓名、性格、外貌、背景等。"
    parameters: dict = PydanticField(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(查询), update(修改), delete(删除), list(列出所有)",
                    "enum": ["create", "query", "update", "delete", "list"],
                },
                "character_id": {
                    "type": "string",
                    "description": "角色ID，query/update/delete时必填",
                },
                "name": {
                    "type": "string",
                    "description": "角色姓名，create/update时使用",
                },
                "personality": {
                    "type": "string",
                    "description": "角色性格描述，create/update时使用",
                },
                "appearance": {
                    "type": "string",
                    "description": "角色外貌描述，create/update时使用",
                },
                "background": {
                    "type": "string",
                    "description": "角色背景故事，create/update时使用",
                },
                "notes": {
                    "type": "string",
                    "description": "角色备注，create/update时使用",
                },
            },
            "required": ["action"],
        }
    )
    storage: Optional[NovelStorage] = field(default=None, repr=False)

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        storage = self.storage
        if storage is None:
            return "错误：存储未初始化。"
        novel = await storage.get_active_novel(context.context.event.unified_msg_origin)
        if novel is None:
            return "错误：当前没有激活的小说。"
        action = kwargs.get("action", "")
        if action == "create":
            char = Character(
                name=kwargs.get("name", ""),
                personality=kwargs.get("personality", ""),
                appearance=kwargs.get("appearance", ""),
                background=kwargs.get("background", ""),
                notes=kwargs.get("notes", ""),
            )
            novel.characters.append(char)
            await storage.save_novel(novel)
            return f"角色「{char.name}」已创建，ID: {char.id}"
        elif action == "query":
            cid = kwargs.get("character_id", "")
            for c in novel.characters:
                if c.id == cid:
                    return json.dumps(
                        {
                            "id": c.id,
                            "name": c.name,
                            "personality": c.personality,
                            "appearance": c.appearance,
                            "background": c.background,
                            "notes": c.notes,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {cid} 的角色"
        elif action == "update":
            cid = kwargs.get("character_id", "")
            for c in novel.characters:
                if c.id == cid:
                    c.apply_updates(kwargs)
                    await storage.save_novel(novel)
                    return f"角色「{c.name}」已更新"
            return f"未找到ID为 {cid} 的角色"
        elif action == "delete":
            cid = kwargs.get("character_id", "")
            before = len(novel.characters)
            novel.characters = [c for c in novel.characters if c.id != cid]
            if len(novel.characters) < before:
                await storage.save_novel(novel)
                return "角色已删除"
            return f"未找到ID为 {cid} 的角色"
        elif action == "list":
            if not novel.characters:
                return "暂无角色"
            result = []
            for c in novel.characters:
                result.append(
                    f"- {c.name}(ID:{c.id}): {c.personality[:50] if c.personality else '无性格描述'}"
                )
            return "\n".join(result)
        return "未知操作"


@dataclass
class RelationshipTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_relationship"
    description: str = "管理小说中角色之间的关系。支持创建、查询、修改、删除角色间关系，包括关系类型和描述。"
    parameters: dict = PydanticField(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(查询), update(修改), delete(删除), list(列出所有)",
                    "enum": ["create", "query", "update", "delete", "list"],
                },
                "relationship_id": {
                    "type": "string",
                    "description": "关系ID，query/update/delete时必填",
                },
                "character_a": {
                    "type": "string",
                    "description": "角色A的姓名或ID，create/update时使用",
                },
                "character_b": {
                    "type": "string",
                    "description": "角色B的姓名或ID，create/update时使用",
                },
                "relation_type": {
                    "type": "string",
                    "description": "关系类型（如朋友、敌人、恋人等），create/update时使用",
                },
                "description": {
                    "type": "string",
                    "description": "关系描述，create/update时使用",
                },
            },
            "required": ["action"],
        }
    )
    storage: Optional[NovelStorage] = field(default=None, repr=False)

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        storage = self.storage
        if storage is None:
            return "错误：存储未初始化。"
        novel = await storage.get_active_novel(context.context.event.unified_msg_origin)
        if novel is None:
            return "错误：当前没有激活的小说。"
        action = kwargs.get("action", "")
        if action == "create":
            rel = Relationship(
                character_a=kwargs.get("character_a", ""),
                character_b=kwargs.get("character_b", ""),
                relation_type=kwargs.get("relation_type", ""),
                description=kwargs.get("description", ""),
            )
            novel.relationships.append(rel)
            await storage.save_novel(novel)
            return f"关系已创建，ID: {rel.id}"
        elif action == "query":
            rid = kwargs.get("relationship_id", "")
            for r in novel.relationships:
                if r.id == rid:
                    return json.dumps(
                        {
                            "id": r.id,
                            "character_a": r.character_a,
                            "character_b": r.character_b,
                            "relation_type": r.relation_type,
                            "description": r.description,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {rid} 的关系"
        elif action == "update":
            rid = kwargs.get("relationship_id", "")
            for r in novel.relationships:
                if r.id == rid:
                    r.apply_updates(kwargs)
                    await storage.save_novel(novel)
                    return "关系已更新"
            return f"未找到ID为 {rid} 的关系"
        elif action == "delete":
            rid = kwargs.get("relationship_id", "")
            before = len(novel.relationships)
            novel.relationships = [r for r in novel.relationships if r.id != rid]
            if len(novel.relationships) < before:
                await storage.save_novel(novel)
                return "关系已删除"
            return f"未找到ID为 {rid} 的关系"
        elif action == "list":
            if not novel.relationships:
                return "暂无角色关系"
            result = []
            for r in novel.relationships:
                result.append(
                    f"- {r.character_a} ↔ {r.character_b}({r.relation_type}): {r.description[:50] if r.description else '无描述'}"
                )
            return "\n".join(result)
        return "未知操作"


@dataclass
class EventTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_event"
    description: str = "管理小说中的事件。支持创建、查询、修改、删除事件，包括事件名、时间线位置、描述、涉及角色等。"
    parameters: dict = PydanticField(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(查询), update(修改), delete(删除), list(列出所有)",
                    "enum": ["create", "query", "update", "delete", "list"],
                },
                "event_id": {
                    "type": "string",
                    "description": "事件ID，query/update/delete时必填",
                },
                "name": {
                    "type": "string",
                    "description": "事件名称，create/update时使用",
                },
                "timeline_position": {
                    "type": "string",
                    "description": "时间线位置，create/update时使用",
                },
                "description": {
                    "type": "string",
                    "description": "事件描述，create/update时使用",
                },
                "involved_characters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "涉及角色的姓名或ID列表，create/update时使用",
                },
            },
            "required": ["action"],
        }
    )
    storage: Optional[NovelStorage] = field(default=None, repr=False)

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        storage = self.storage
        if storage is None:
            return "错误：存储未初始化。"
        novel = await storage.get_active_novel(context.context.event.unified_msg_origin)
        if novel is None:
            return "错误：当前没有激活的小说。"
        action = kwargs.get("action", "")
        if action == "create":
            evt = Event(
                name=kwargs.get("name", ""),
                timeline_position=kwargs.get("timeline_position", ""),
                description=kwargs.get("description", ""),
                involved_characters=kwargs.get("involved_characters", []),
            )
            novel.events.append(evt)
            await storage.save_novel(novel)
            return f"事件「{evt.name}」已创建，ID: {evt.id}"
        elif action == "query":
            eid = kwargs.get("event_id", "")
            for e in novel.events:
                if e.id == eid:
                    return json.dumps(
                        {
                            "id": e.id,
                            "name": e.name,
                            "timeline_position": e.timeline_position,
                            "description": e.description,
                            "involved_characters": e.involved_characters,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {eid} 的事件"
        elif action == "update":
            eid = kwargs.get("event_id", "")
            for e in novel.events:
                if e.id == eid:
                    e.apply_updates(kwargs)
                    await storage.save_novel(novel)
                    return f"事件「{e.name}」已更新"
            return f"未找到ID为 {eid} 的事件"
        elif action == "delete":
            eid = kwargs.get("event_id", "")
            before = len(novel.events)
            novel.events = [e for e in novel.events if e.id != eid]
            if len(novel.events) < before:
                await storage.save_novel(novel)
                return "事件已删除"
            return f"未找到ID为 {eid} 的事件"
        elif action == "list":
            if not novel.events:
                return "暂无事件"
            result = []
            for e in novel.events:
                chars = (
                    ", ".join(e.involved_characters) if e.involved_characters else "无"
                )
                result.append(
                    f"- {e.name}(ID:{e.id}) [{e.timeline_position}]: {e.description[:50] if e.description else '无描述'} (涉及: {chars})"
                )
            return "\n".join(result)
        return "未知操作"


@dataclass
class OutlineTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_outline"
    description: str = "管理小说的剧情大纲。支持创建、查询、修改、删除剧情大纲，包括章节规划和情节走向。"
    parameters: dict = PydanticField(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(查询), update(修改), delete(删除), list(列出所有)",
                    "enum": ["create", "query", "update", "delete", "list"],
                },
                "outline_id": {
                    "type": "string",
                    "description": "大纲ID，query/update/delete时必填",
                },
                "title": {
                    "type": "string",
                    "description": "大纲标题，create/update时使用",
                },
                "chapter_plan": {
                    "type": "string",
                    "description": "章节规划，create/update时使用",
                },
                "plot_direction": {
                    "type": "string",
                    "description": "情节走向，create/update时使用",
                },
                "notes": {
                    "type": "string",
                    "description": "备注，create/update时使用",
                },
            },
            "required": ["action"],
        }
    )
    storage: Optional[NovelStorage] = field(default=None, repr=False)

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        storage = self.storage
        if storage is None:
            return "错误：存储未初始化。"
        novel = await storage.get_active_novel(context.context.event.unified_msg_origin)
        if novel is None:
            return "错误：当前没有激活的小说。"
        action = kwargs.get("action", "")
        if action == "create":
            out = Outline(
                title=kwargs.get("title", ""),
                chapter_plan=kwargs.get("chapter_plan", ""),
                plot_direction=kwargs.get("plot_direction", ""),
                notes=kwargs.get("notes", ""),
            )
            novel.outlines.append(out)
            await storage.save_novel(novel)
            return f"大纲「{out.title}」已创建，ID: {out.id}"
        elif action == "query":
            oid = kwargs.get("outline_id", "")
            for o in novel.outlines:
                if o.id == oid:
                    return json.dumps(
                        {
                            "id": o.id,
                            "title": o.title,
                            "chapter_plan": o.chapter_plan,
                            "plot_direction": o.plot_direction,
                            "notes": o.notes,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {oid} 的大纲"
        elif action == "update":
            oid = kwargs.get("outline_id", "")
            for o in novel.outlines:
                if o.id == oid:
                    o.apply_updates(kwargs)
                    await storage.save_novel(novel)
                    return f"大纲「{o.title}」已更新"
            return f"未找到ID为 {oid} 的大纲"
        elif action == "delete":
            oid = kwargs.get("outline_id", "")
            before = len(novel.outlines)
            novel.outlines = [o for o in novel.outlines if o.id != oid]
            if len(novel.outlines) < before:
                await storage.save_novel(novel)
                return "大纲已删除"
            return f"未找到ID为 {oid} 的大纲"
        elif action == "list":
            if not novel.outlines:
                return "暂无剧情大纲"
            result = []
            for o in novel.outlines:
                result.append(
                    f"- {o.title}(ID:{o.id}): 规划={o.chapter_plan[:50] if o.chapter_plan else '无'} | 走向={o.plot_direction[:50] if o.plot_direction else '无'}"
                )
            return "\n".join(result)
        return "未知操作"


@dataclass
class ChapterTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_chapter"
    description: str = (
        "管理小说的章节内容。支持创建、查询、修改章节，包括章节号、标题和正文内容。"
    )
    parameters: dict = PydanticField(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(查询), update(修改), list(列出所有)",
                    "enum": ["create", "query", "update", "list"],
                },
                "chapter_id": {
                    "type": "string",
                    "description": "章节ID，query/update时必填",
                },
                "number": {
                    "type": "integer",
                    "description": "章节号，create/update时使用",
                },
                "title": {
                    "type": "string",
                    "description": "章节标题，create/update时使用",
                },
                "content": {
                    "type": "string",
                    "description": "章节正文内容，create/update时使用",
                },
            },
            "required": ["action"],
        }
    )
    storage: Optional[NovelStorage] = field(default=None, repr=False)

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        storage = self.storage
        if storage is None:
            return "错误：存储未初始化。"
        novel = await storage.get_active_novel(context.context.event.unified_msg_origin)
        if novel is None:
            return "错误：当前没有激活的小说。"
        action = kwargs.get("action", "")
        if action == "create":
            ch = Chapter(
                number=kwargs.get("number", len(novel.chapters) + 1),
                title=kwargs.get("title", ""),
                content=kwargs.get("content", ""),
            )
            novel.chapters.append(ch)
            novel.chapters.sort(key=lambda x: x.number)
            await storage.save_novel(novel)
            return f"第{ch.number}章「{ch.title}」已创建，ID: {ch.id}"
        elif action == "query":
            cid = kwargs.get("chapter_id", "")
            for ch in novel.chapters:
                if ch.id == cid:
                    return json.dumps(
                        {
                            "id": ch.id,
                            "number": ch.number,
                            "title": ch.title,
                            "content": ch.content,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {cid} 的章节"
        elif action == "update":
            cid = kwargs.get("chapter_id", "")
            for ch in novel.chapters:
                if ch.id == cid:
                    ch.apply_updates(kwargs)
                    novel.chapters.sort(key=lambda x: x.number)
                    await storage.save_novel(novel)
                    return f"第{ch.number}章「{ch.title}」已更新"
            return f"未找到ID为 {cid} 的章节"
        elif action == "list":
            if not novel.chapters:
                return "暂无章节"
            result = []
            for ch in novel.chapters:
                content_preview = (
                    ch.content[:50] + "..." if len(ch.content) > 50 else ch.content
                )
                result.append(
                    f"- 第{ch.number}章 {ch.title}(ID:{ch.id}): {content_preview}"
                )
            return "\n".join(result)
        return "未知操作"


NOVEL_TOOLS = [CharacterTool, RelationshipTool, EventTool, OutlineTool, ChapterTool]
