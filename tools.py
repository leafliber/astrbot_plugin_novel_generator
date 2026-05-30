from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from .models import Character, Chapter, Event, Outline, Relationship, WorldSetting
from .storage import NovelStorage


@dataclass
class CharacterTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_character"
    description: str = "管理小说中的角色画像。支持创建、查询、修改、删除角色信息，包括姓名、性格、外貌、背景等。"
    parameters: dict = field(
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
                novel.relationships = [
                    r for r in novel.relationships
                    if r.character_a != cid and r.character_b != cid
                ]
                for e in novel.events:
                    e.involved_characters = [
                        c for c in e.involved_characters if c != cid
                    ]
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
    parameters: dict = field(
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
            raw_a = kwargs.get("character_a", "")
            raw_b = kwargs.get("character_b", "")
            id_a = novel.resolve_character_id(raw_a)
            id_b = novel.resolve_character_id(raw_b)
            if not id_a:
                return f"错误：未找到角色「{raw_a}」，请先创建该角色或使用正确的ID。"
            if not id_b:
                return f"错误：未找到角色「{raw_b}」，请先创建该角色或使用正确的ID。"
            rel = Relationship(
                character_a=id_a,
                character_b=id_b,
                relation_type=kwargs.get("relation_type", ""),
                description=kwargs.get("description", ""),
            )
            novel.relationships.append(rel)
            await storage.save_novel(novel)
            name_a = novel.character_name_by_id(id_a)
            name_b = novel.character_name_by_id(id_b)
            return f"关系已创建：{name_a} ↔ {name_b}，ID: {rel.id}"
        elif action == "query":
            rid = kwargs.get("relationship_id", "")
            for r in novel.relationships:
                if r.id == rid:
                    return json.dumps(
                        {
                            "id": r.id,
                            "character_a": novel.character_name_by_id(r.character_a),
                            "character_a_id": r.character_a,
                            "character_b": novel.character_name_by_id(r.character_b),
                            "character_b_id": r.character_b,
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
                    resolved = {}
                    if "character_a" in kwargs:
                        id_a = novel.resolve_character_id(kwargs["character_a"])
                        if not id_a:
                            return f"错误：未找到角色「{kwargs['character_a']}」。"
                        resolved["character_a"] = id_a
                    if "character_b" in kwargs:
                        id_b = novel.resolve_character_id(kwargs["character_b"])
                        if not id_b:
                            return f"错误：未找到角色「{kwargs['character_b']}」。"
                        resolved["character_b"] = id_b
                    for k in ("relation_type", "description"):
                        if k in kwargs:
                            resolved[k] = kwargs[k]
                    r.apply_updates(resolved)
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
                name_a = novel.character_name_by_id(r.character_a)
                name_b = novel.character_name_by_id(r.character_b)
                result.append(
                    f"- {name_a} ↔ {name_b}(ID:{r.id}) [{r.relation_type}]: {r.description[:50] if r.description else '无描述'}"
                )
            return "\n".join(result)
        return "未知操作"


@dataclass
class EventTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_event"
    description: str = "管理小说中的事件。支持创建、查询、修改、删除事件，包括事件名、时间线位置、描述、涉及角色等。"
    parameters: dict = field(
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
            raw_chars = kwargs.get("involved_characters", [])
            resolved_chars = []
            unresolved = []
            for ref in raw_chars:
                cid = novel.resolve_character_id(ref)
                if cid:
                    resolved_chars.append(cid)
                else:
                    unresolved.append(ref)
            if unresolved:
                return f"错误：未找到角色：{', '.join(unresolved)}，请先创建或使用正确的ID。"
            evt = Event(
                name=kwargs.get("name", ""),
                timeline_position=kwargs.get("timeline_position", ""),
                description=kwargs.get("description", ""),
                involved_characters=resolved_chars,
            )
            novel.events.append(evt)
            await storage.save_novel(novel)
            return f"事件「{evt.name}」已创建，ID: {evt.id}"
        elif action == "query":
            eid = kwargs.get("event_id", "")
            for e in novel.events:
                if e.id == eid:
                    char_names = [novel.character_name_by_id(c) for c in e.involved_characters]
                    return json.dumps(
                        {
                            "id": e.id,
                            "name": e.name,
                            "timeline_position": e.timeline_position,
                            "description": e.description,
                            "involved_characters": char_names,
                            "involved_character_ids": e.involved_characters,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {eid} 的事件"
        elif action == "update":
            eid = kwargs.get("event_id", "")
            for e in novel.events:
                if e.id == eid:
                    resolved = {}
                    for k in ("name", "timeline_position", "description"):
                        if k in kwargs:
                            resolved[k] = kwargs[k]
                    if "involved_characters" in kwargs:
                        resolved_chars = []
                        unresolved = []
                        for ref in kwargs["involved_characters"]:
                            cid = novel.resolve_character_id(ref)
                            if cid:
                                resolved_chars.append(cid)
                            else:
                                unresolved.append(ref)
                        if unresolved:
                            return f"错误：未找到角色：{', '.join(unresolved)}。"
                        resolved["involved_characters"] = resolved_chars
                    e.apply_updates(resolved)
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
                char_names = [novel.character_name_by_id(c) for c in e.involved_characters]
                chars = ", ".join(char_names) if char_names else "无"
                result.append(
                    f"- {e.name}(ID:{e.id}) [{e.timeline_position}]: {e.description[:50] if e.description else '无描述'} (涉及: {chars})"
                )
            return "\n".join(result)
        return "未知操作"


@dataclass
class OutlineTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_outline"
    description: str = "管理小说的剧情大纲。支持创建、查询、修改、删除剧情大纲，包括章节规划和情节走向。"
    parameters: dict = field(
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
                "parent_id": {
                    "type": "string",
                    "description": "父大纲ID，用于构建层级关系，留空表示顶层大纲，create/update时使用",
                },
                "order": {
                    "type": "integer",
                    "description": "排序序号，数字越小越靠前，create/update时使用",
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
                parent_id=kwargs.get("parent_id", ""),
                order=kwargs.get("order", len(novel.outlines) + 1),
            )
            novel.outlines.append(out)
            novel.outlines.sort(key=lambda x: x.order)
            await storage.save_novel(novel)
            parent_info = f" (父: {out.parent_id})" if out.parent_id else ""
            return f"大纲「{out.title}」已创建，ID: {out.id}{parent_info}"
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
                            "parent_id": o.parent_id,
                            "order": o.order,
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
            novel.outlines.sort(key=lambda x: x.order)
            by_parent: dict[str, list] = {}
            for o in novel.outlines:
                by_parent.setdefault(o.parent_id, []).append(o)
            result = []

            def _render_tree(parent_id: str, indent: int = 0):
                children = by_parent.get(parent_id, [])
                for o in children:
                    prefix = "  " * indent + ("└ " if indent > 0 else "- ")
                    result.append(
                        f"{prefix}{o.title}(ID:{o.id}): 规划={o.chapter_plan[:50] if o.chapter_plan else '无'} | 走向={o.plot_direction[:50] if o.plot_direction else '无'}"
                    )
                    _render_tree(o.id, indent + 1)

            _render_tree("")
            return "\n".join(result)
        return "未知操作"


@dataclass
class ChapterTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_chapter"
    description: str = (
        "管理小说的章节内容。支持创建、查询、修改章节，包括章节号、标题和正文内容。"
        "重要：章节正文可能很长，请使用以下策略：1) 先用create创建章节（content留空或只写开头），"
        "2) 然后多次使用append_content分段追加正文内容，每次追加一段（约500-1000字），"
        "3) 使用update修改标题、状态、摘要等元数据。切勿在单次调用中传入完整长文。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(查询), update(修改), delete(删除), list(列出所有), append_content(追加正文内容到指定章节)",
                    "enum": ["create", "query", "update", "delete", "list", "append_content"],
                },
                "chapter_id": {
                    "type": "string",
                    "description": "章节ID，query/update/delete/append_content时必填",
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
                    "description": "章节正文内容，create时使用（建议仅写入开头，后续用append_content追加）",
                },
                "status": {
                    "type": "string",
                    "description": "章节状态：draft(草稿), review(审核中), final(定稿)，create/update时使用",
                    "enum": ["draft", "review", "final"],
                },
                "summary": {
                    "type": "string",
                    "description": "章节摘要，create/update时使用",
                },
                "append_text": {
                    "type": "string",
                    "description": "要追加到章节末尾的正文内容（约500-1000字），append_content时必填",
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
            ch_number = kwargs.get("number", len(novel.chapters) + 1)
            existing_numbers = {ch.number for ch in novel.chapters}
            if ch_number in existing_numbers:
                return f"错误：第{ch_number}章已存在，请使用其他章节号或省略number让系统自动分配。"
            ch = Chapter(
                number=ch_number,
                title=kwargs.get("title", ""),
                content=kwargs.get("content", ""),
                status=kwargs.get("status", "draft"),
                summary=kwargs.get("summary", ""),
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
                            "status": ch.status,
                            "summary": ch.summary,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {cid} 的章节"
        elif action == "update":
            cid = kwargs.get("chapter_id", "")
            for ch in novel.chapters:
                if ch.id == cid:
                    update_data = {k: v for k, v in kwargs.items() if k != "content"}
                    ch.apply_updates(update_data)
                    novel.chapters.sort(key=lambda x: x.number)
                    await storage.save_novel(novel)
                    return f"第{ch.number}章「{ch.title}」已更新"
            return f"未找到ID为 {cid} 的章节"
        elif action == "delete":
            cid = kwargs.get("chapter_id", "")
            before = len(novel.chapters)
            novel.chapters = [ch for ch in novel.chapters if ch.id != cid]
            if len(novel.chapters) < before:
                await storage.save_novel(novel)
                return "章节已删除"
            return f"未找到ID为 {cid} 的章节"
        elif action == "append_content":
            cid = kwargs.get("chapter_id", "")
            append_text = kwargs.get("append_text", "")
            if not append_text:
                return "错误：append_text不能为空。"
            for ch in novel.chapters:
                if ch.id == cid:
                    if ch.content:
                        ch.content += "\n" + append_text
                    else:
                        ch.content = append_text
                    await storage.save_novel(novel)
                    content_len = len(ch.content)
                    return f"第{ch.number}章「{ch.title}」已追加内容，当前总字数：{content_len}"
            return f"未找到ID为 {cid} 的章节"
        elif action == "list":
            if not novel.chapters:
                return "暂无章节"
            result = []
            for ch in novel.chapters:
                status_label = {"draft": "草稿", "review": "审核中", "final": "定稿"}.get(ch.status, ch.status)
                summary_info = f" | 摘要: {ch.summary[:40]}" if ch.summary else ""
                result.append(
                    f"- 第{ch.number}章 {ch.title}(ID:{ch.id}) [{status_label}]{summary_info}"
                )
            return "\n".join(result)
        return "未知操作"


@dataclass
class WorldSettingTool(FunctionTool[AstrAgentContext]):
    name: str = "manage_world_setting"
    description: str = "管理小说的世界观设定。支持创建、查询、修改、删除世界观设定，包括时代背景、地理、魔法体系、社会结构等。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(查询), update(修改), delete(删除), list(列出所有)",
                    "enum": ["create", "query", "update", "delete", "list"],
                },
                "setting_id": {
                    "type": "string",
                    "description": "设定ID，query/update/delete时必填",
                },
                "category": {
                    "type": "string",
                    "description": "设定分类（如时代、地理、魔法体系、社会、种族等），create/update时使用",
                },
                "name": {
                    "type": "string",
                    "description": "设定名称，create/update时使用",
                },
                "description": {
                    "type": "string",
                    "description": "设定详细描述，create/update时使用",
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
            ws = WorldSetting(
                category=kwargs.get("category", ""),
                name=kwargs.get("name", ""),
                description=kwargs.get("description", ""),
            )
            novel.world_settings.append(ws)
            await storage.save_novel(novel)
            return f"世界观设定「{ws.name}」已创建，ID: {ws.id}"
        elif action == "query":
            sid = kwargs.get("setting_id", "")
            for ws in novel.world_settings:
                if ws.id == sid:
                    return json.dumps(
                        {
                            "id": ws.id,
                            "category": ws.category,
                            "name": ws.name,
                            "description": ws.description,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {sid} 的世界观设定"
        elif action == "update":
            sid = kwargs.get("setting_id", "")
            for ws in novel.world_settings:
                if ws.id == sid:
                    ws.apply_updates(kwargs)
                    await storage.save_novel(novel)
                    return f"世界观设定「{ws.name}」已更新"
            return f"未找到ID为 {sid} 的世界观设定"
        elif action == "delete":
            sid = kwargs.get("setting_id", "")
            before = len(novel.world_settings)
            novel.world_settings = [ws for ws in novel.world_settings if ws.id != sid]
            if len(novel.world_settings) < before:
                await storage.save_novel(novel)
                return "世界观设定已删除"
            return f"未找到ID为 {sid} 的世界观设定"
        elif action == "list":
            if not novel.world_settings:
                return "暂无世界观设定"
            result = []
            for ws in novel.world_settings:
                result.append(
                    f"- [{ws.category}] {ws.name}(ID:{ws.id}): {ws.description[:80] if ws.description else '无描述'}"
                )
            return "\n".join(result)
        return "未知操作"


NOVEL_TOOLS = [CharacterTool, RelationshipTool, EventTool, OutlineTool, ChapterTool, WorldSettingTool]
