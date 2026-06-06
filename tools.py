from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import ClassVar, Optional

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from .models import Character, Chapter, Event, Novel, Outline, Relationship, WorldSetting, chapter_display
from .storage import NovelStorage

_STATUS_LABELS = {"draft": "草稿", "review": "审核中", "final": "定稿"}


def _next_chapter_number(novel: Novel) -> int:
    return max((ch.number for ch in novel.chapters), default=0) + 1


def _next_chapter_order(novel: Novel) -> float:
    return max((ch.order for ch in novel.chapters), default=0.0) + 1.0


@dataclass
class BaseNovelTool(FunctionTool[AstrAgentContext]):
    storage: Optional[NovelStorage] = field(default=None, repr=False)
    session_id: str = ""
    _needs_content: ClassVar[bool] = False

    async def _get_novel(self, context: ContextWrapper[AstrAgentContext], *, load_content: bool | None = None) -> tuple[Optional[Novel], Optional[str]]:
        if self.storage is None:
            return None, "错误：存储未初始化。"
        lc = load_content if load_content is not None else self._needs_content
        novel = await self.storage.get_active_novel(
            self.session_id,
            load_content=lc,
        )
        if novel is None:
            return None, "错误：当前没有激活的小说。"
        return novel, None

    async def _save(self, novel: Novel) -> None:
        await self.storage.save_novel(novel, save_content=self._needs_content)

    @staticmethod
    def _editable_kwargs(model_cls: type, kwargs: dict) -> dict:
        return {k: v for k, v in kwargs.items() if k in model_cls.EDITABLE_FIELDS}


@dataclass
class CharacterTool(BaseNovelTool):
    name: str = "manage_character"
    description: str = "管理小说中的角色画像。支持创建、查询、修改、删除、列出和搜索角色信息，包括姓名、性格、外貌、背景等。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(按ID查询), update(修改), delete(删除), list(列出所有), search(按名称/描述模糊搜索)",
                    "enum": ["create", "query", "update", "delete", "list", "search"],
                },
                "character_id": {
                    "type": "string",
                    "description": "角色ID。query/update/delete 时必填。",
                },
                "name": {
                    "type": "string",
                    "description": "角色姓名。create 时必填，update 时可选。",
                },
                "personality": {
                    "type": "string",
                    "description": "角色性格描述。create/update 时可选。",
                },
                "appearance": {
                    "type": "string",
                    "description": "角色外貌描述。create/update 时可选。",
                },
                "background": {
                    "type": "string",
                    "description": "角色背景故事。create/update 时可选。",
                },
                "notes": {
                    "type": "string",
                    "description": "角色备注。create/update 时可选。",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，search 时必填。在姓名、性格、背景等字段中模糊匹配。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        novel, err = await self._get_novel(context)
        if err:
            return err
        action = kwargs.get("action", "")
        if action == "create":
            char_name = kwargs.get("name", "")
            duplicates = [c for c in novel.characters if c.name == char_name and char_name]
            if duplicates:
                dup_ids = ", ".join(c.id for c in duplicates)
                warning = f"\n⚠ 注意：已存在同名角色（ID: {dup_ids}），引用此角色时请使用 ID 而非姓名。"
            else:
                warning = ""
            char = Character(
                name=char_name,
                personality=kwargs.get("personality", ""),
                appearance=kwargs.get("appearance", ""),
                background=kwargs.get("background", ""),
                notes=kwargs.get("notes", ""),
            )
            novel.characters.append(char)
            await self._save(novel)
            return f"角色「{char.name}」已创建，ID: {char.id}{warning}"
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
                    c.apply_updates(self._editable_kwargs(Character, kwargs))
                    await self._save(novel)
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
                await self._save(novel)
                return "角色已删除，相关关系和事件引用已自动清理。请检查大纲描述中是否有需要同步修改的该角色引用。"
            return f"未找到ID为 {cid} 的角色"
        elif action == "search":
            keyword = kwargs.get("keyword", "")
            if not keyword:
                return "请提供搜索关键词"
            result = []
            for c in novel.characters:
                fields = [c.name, c.personality, c.appearance, c.background, c.notes]
                if any(keyword in f for f in fields):
                    result.append(
                        f"- {c.name}(ID:{c.id}): {c.personality[:60] if c.personality else '无性格描述'}"
                    )
            return "\n".join(result) if result else f"未找到包含「{keyword}」的角色"
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
class RelationshipTool(BaseNovelTool):
    name: str = "manage_relationship"
    description: str = "管理小说中角色之间的关系。支持创建、查询、修改、删除、列出和搜索角色间关系，包括关系类型和描述。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(按ID查询), update(修改), delete(删除), list(列出所有), search(按类型/描述模糊搜索)",
                    "enum": ["create", "query", "update", "delete", "list", "search"],
                },
                "relationship_id": {
                    "type": "string",
                    "description": "关系ID。query/update/delete 时必填。",
                },
                "character_a": {
                    "type": "string",
                    "description": "角色A的姓名或ID。create/update 时使用。",
                },
                "character_b": {
                    "type": "string",
                    "description": "角色B的姓名或ID。create/update 时使用。",
                },
                "relation_type": {
                    "type": "string",
                    "description": "关系类型。常见：朋友、敌人、恋人、师徒、亲人、同僚、竞争对手、主从等，也可自定义。create/update 时使用。",
                },
                "description": {
                    "type": "string",
                    "description": "关系描述。create/update 时使用。",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，search 时必填。在关系类型、描述、角色姓名中模糊匹配。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        novel, err = await self._get_novel(context)
        if err:
            return err
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
            await self._save(novel)
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
                    await self._save(novel)
                    return "关系已更新"
            return f"未找到ID为 {rid} 的关系"
        elif action == "delete":
            rid = kwargs.get("relationship_id", "")
            before = len(novel.relationships)
            novel.relationships = [r for r in novel.relationships if r.id != rid]
            if len(novel.relationships) < before:
                await self._save(novel)
                return "关系已删除"
            return f"未找到ID为 {rid} 的关系"
        elif action == "search":
            keyword = kwargs.get("keyword", "")
            if not keyword:
                return "请提供搜索关键词"
            result = []
            for r in novel.relationships:
                name_a = novel.character_name_by_id(r.character_a)
                name_b = novel.character_name_by_id(r.character_b)
                fields = [r.relation_type, r.description, name_a, name_b]
                if any(keyword in f for f in fields):
                    result.append(
                        f"- {name_a} ↔ {name_b}(ID:{r.id}) [{r.relation_type}]: {r.description[:50] if r.description else '无描述'}"
                    )
            return "\n".join(result) if result else f"未找到包含「{keyword}」的关系"
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
class EventTool(BaseNovelTool):
    name: str = "manage_event"
    description: str = "管理小说中的事件。支持创建、查询、修改、删除、列出和搜索事件，包括事件名、时间线位置、描述、涉及角色等。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(按ID查询), update(修改), delete(删除), list(列出所有), search(按名称/描述模糊搜索)",
                    "enum": ["create", "query", "update", "delete", "list", "search"],
                },
                "event_id": {
                    "type": "string",
                    "description": "事件ID。query/update/delete 时必填。",
                },
                "name": {
                    "type": "string",
                    "description": "事件名称。create 时必填，update 时可选。",
                },
                "timeline_position": {
                    "type": "string",
                    "description": "时间线位置（如「第一章」「故事前期」「大战之前」等）。create/update 时可选。",
                },
                "description": {
                    "type": "string",
                    "description": "事件描述。create/update 时可选。",
                },
                "involved_characters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "涉及角色的姓名或ID列表。create/update 时可选。",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，search 时必填。在事件名、时间线位置、描述中模糊匹配。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        novel, err = await self._get_novel(context)
        if err:
            return err
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
            await self._save(novel)
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
                    await self._save(novel)
                    return f"事件「{e.name}」已更新"
            return f"未找到ID为 {eid} 的事件"
        elif action == "delete":
            eid = kwargs.get("event_id", "")
            before = len(novel.events)
            novel.events = [e for e in novel.events if e.id != eid]
            if len(novel.events) < before:
                await self._save(novel)
                return "事件已删除"
            return f"未找到ID为 {eid} 的事件"
        elif action == "search":
            keyword = kwargs.get("keyword", "")
            if not keyword:
                return "请提供搜索关键词"
            result = []
            for e in novel.events:
                fields = [e.name, e.timeline_position, e.description]
                if any(keyword in f for f in fields):
                    char_names = [novel.character_name_by_id(c) for c in e.involved_characters]
                    chars = ", ".join(char_names) if char_names else "无"
                    result.append(
                        f"- {e.name}(ID:{e.id}) [{e.timeline_position}]: {e.description[:50] if e.description else '无描述'} (涉及: {chars})"
                    )
            return "\n".join(result) if result else f"未找到包含「{keyword}」的事件"
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
class OutlineTool(BaseNovelTool):
    name: str = "manage_outline"
    description: str = "管理小说的剧情大纲。支持创建、查询、修改、删除、列出和搜索剧情大纲，包括章节规划和情节走向。支持层级结构。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(按ID查询), update(修改), delete(删除), list(列出所有，树形展示), search(按标题/走向模糊搜索)",
                    "enum": ["create", "query", "update", "delete", "list", "search"],
                },
                "outline_id": {
                    "type": "string",
                    "description": "大纲ID。query/update/delete 时必填。",
                },
                "title": {
                    "type": "string",
                    "description": "大纲标题。create 时必填，update 时可选。",
                },
                "chapter_plan": {
                    "type": "string",
                    "description": "章节规划（如「1-5章」）。create/update 时可选。",
                },
                "plot_direction": {
                    "type": "string",
                    "description": "情节走向描述。create/update 时可选。",
                },
                "notes": {
                    "type": "string",
                    "description": "备注。create/update 时可选。",
                },
                "parent_id": {
                    "type": "string",
                    "description": "父大纲ID，用于构建层级关系。留空表示顶层大纲。create/update 时可选。",
                },
                "order": {
                    "type": "integer",
                    "description": "排序序号，数字越小越靠前。create/update 时可选，默认追加到末尾。",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，search 时必填。在标题、章节规划、情节走向、备注中模糊匹配。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        novel, err = await self._get_novel(context)
        if err:
            return err
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
            await self._save(novel)
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
                    o.apply_updates(self._editable_kwargs(Outline, kwargs))
                    await self._save(novel)
                    return f"大纲「{o.title}」已更新"
            return f"未找到ID为 {oid} 的大纲"
        elif action == "delete":
            oid = kwargs.get("outline_id", "")
            before = len(novel.outlines)
            novel.outlines = [o for o in novel.outlines if o.id != oid]
            if len(novel.outlines) < before:
                await self._save(novel)
                return "大纲已删除"
            return f"未找到ID为 {oid} 的大纲"
        elif action == "search":
            keyword = kwargs.get("keyword", "")
            if not keyword:
                return "请提供搜索关键词"
            result = []
            for o in novel.outlines:
                fields = [o.title, o.chapter_plan, o.plot_direction, o.notes]
                if any(keyword in f for f in fields):
                    result.append(
                        f"- {o.title}(ID:{o.id}): 规划={o.chapter_plan[:50] if o.chapter_plan else '无'} | 走向={o.plot_direction[:50] if o.plot_direction else '无'}"
                    )
            return "\n".join(result) if result else f"未找到包含「{keyword}」的大纲"
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
class ChapterTool(BaseNovelTool):
    _needs_content: ClassVar[bool] = True

    name: str = "manage_chapter"
    description: str = (
        "管理小说的章节内容。\n"
        "\n"
        "## 正文写入策略\n"
        "章节正文较长，必须分段写入：1) create 创建章节（content 留空或只写开头），"
        "2) append_content 分段追加正文（每次约 1500-2500 字），"
        "3) update 修改元数据（update 不会修改 content）。切勿在单次调用中传入完整长文。\n"
        "\n"
        "## 排序机制\n"
        "章节排序由 order 字段控制（数字越小越靠前），与 number（章节号）独立。"
        "number 仅用于显示（如「第3章」），不影响实际排列顺序。\n"
        "\n"
        "## 特殊章节\n"
        "番外、序章、终章等可通过 label 设置自定义显示名（如「番外一·前传」），"
        "设 is_extra=true 可标记为番外（无 label 时显示「番外·标题」）。label 和 is_extra 均可通过 update 随时修改。\n"
        "\n"
        "## 调整顺序\n"
        "- move：移动单个章节，指定 before/after_chapter_id 作为锚点。适合微调。"
        "- reorder：传入完整的章节ID列表重排全部章节。适合大规模调整。\n"
        "\n"
        "## 重编号\n"
        "- renumber：按当前排列顺序，将普通章节的 number 从 1 开始连续编号。"
        "带有 label 或 is_extra=true 的章节不受影响。适合删除章节后消除号码间隙。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(按ID查询), update(修改元数据), delete(删除), list(列出所有), append_content(追加正文到章节末尾), search(按标题/摘要模糊搜索), reorder(整体重排章节顺序), move(单章移动到指定位置), renumber(按排列顺序连续重编章节号)",
                    "enum": ["create", "query", "update", "delete", "list", "append_content", "search", "reorder", "move", "renumber"],
                },
                "chapter_id": {
                    "type": "string",
                    "description": "章节ID。query/update/delete/append_content/move 时必填。",
                },
                "number": {
                    "type": "integer",
                    "description": "章节号（显示用）。create/update 时可选。普通章节默认自动递增。",
                },
                "order": {
                    "type": "number",
                    "description": "排序权重（浮点数），数字越小越靠前。create/update 时可选。reorder/move 会自动管理此字段。",
                },
                "title": {
                    "type": "string",
                    "description": "章节标题。create/update 时可选。",
                },
                "content": {
                    "type": "string",
                    "description": "章节正文内容。仅 create 时使用（建议仅写入开头，后续用append_content追加）。update 不会修改此字段。",
                },
                "status": {
                    "type": "string",
                    "description": "章节状态。create/update 时可选。draft(草稿), review(审核中), final(定稿)。",
                    "enum": ["draft", "review", "final"],
                },
                "summary": {
                    "type": "string",
                    "description": "章节摘要。create/update 时可选。",
                },
                "label": {
                    "type": "string",
                    "description": "自定义显示标签，设置后覆盖默认的「第N章」格式。用于番外（如「番外一·前传」）、序章、终章等特殊章节。create/update 时可选。",
                },
                "is_extra": {
                    "type": "boolean",
                    "description": "是否为番外章节。true时若无label则显示为「番外·标题」。create/update 时可选。",
                },
                "append_text": {
                    "type": "string",
                    "description": "要追加到章节末尾的正文内容（建议每段 300-800 字，一个完整的叙事段落或场景）。append_content 时必填。",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，search 时必填。在章节标题、摘要、label中模糊匹配。不搜索正文内容，如需查看正文请用 query。",
                },
                "chapter_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "完整的章节ID列表，按目标顺序排列。reorder 时必填。",
                },
                "before_chapter_id": {
                    "type": "string",
                    "description": "锚点章节ID，将目标章节移到此章节之前。例如 before=X 表示目标章节排在 X 前面。move 时与 after_chapter_id 二选一。",
                },
                "after_chapter_id": {
                    "type": "string",
                    "description": "锚点章节ID，将目标章节移到此章节之后。例如 after=X 表示目标章节排在 X 后面。move 时与 before_chapter_id 二选一。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        action = kwargs.get("action", "")
        load = False if action in ("list", "search") else None
        novel, err = await self._get_novel(context, load_content=load)
        if err:
            return err
        if action == "create":
            ch_number = kwargs.get("number", _next_chapter_number(novel))
            ch_order = kwargs.get("order", _next_chapter_order(novel))
            existing_numbers = {ch.number for ch in novel.chapters}
            if ch_number in existing_numbers:
                return f"错误：第{ch_number}章已存在，请使用其他章节号或省略number让系统自动分配。"
            ch = Chapter(
                number=ch_number,
                order=ch_order,
                title=kwargs.get("title", ""),
                content=kwargs.get("content", ""),
                status=kwargs.get("status", "draft"),
                summary=kwargs.get("summary", ""),
                label=kwargs.get("label", ""),
                is_extra=kwargs.get("is_extra", False),
            )
            novel.chapters.append(ch)
            novel.chapters.sort(key=lambda x: x.order)
            await self._save(novel)
            display = chapter_display(ch)
            return f"{display}「{ch.title}」已创建，ID: {ch.id}"
        elif action == "query":
            cid = kwargs.get("chapter_id", "")
            for ch in novel.chapters:
                if ch.id == cid:
                    return json.dumps(
                        {
                            "id": ch.id,
                            "number": ch.number,
                            "order": ch.order,
                            "title": ch.title,
                            "content": ch.content,
                            "status": ch.status,
                            "summary": ch.summary,
                            "label": ch.label,
                            "is_extra": ch.is_extra,
                        },
                        ensure_ascii=False,
                    )
            return f"未找到ID为 {cid} 的章节"
        elif action == "update":
            cid = kwargs.get("chapter_id", "")
            for ch in novel.chapters:
                if ch.id == cid:
                    ch.apply_updates(self._editable_kwargs(Chapter, kwargs))
                    novel.chapters.sort(key=lambda x: x.order)
                    await self._save(novel)
                    display = chapter_display(ch)
                    return f"{display}「{ch.title}」元数据已更新（注：update 不会修改正文内容，请使用 append_content 追加正文）"
            return f"未找到ID为 {cid} 的章节"
        elif action == "delete":
            cid = kwargs.get("chapter_id", "")
            before = len(novel.chapters)
            novel.chapters = [ch for ch in novel.chapters if ch.id != cid]
            if len(novel.chapters) < before:
                await self._save(novel)
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
                    await self._save(novel)
                    content_len = len(ch.content)
                    display = chapter_display(ch)
                    return f"{display}「{ch.title}」已追加内容，当前总字数：{content_len}。建议章节正文写完后，使用 update 更新 summary 字段概括本章关键情节和角色状态变化。"
            return f"未找到ID为 {cid} 的章节"
        elif action == "search":
            keyword = kwargs.get("keyword", "")
            if not keyword:
                return "请提供搜索关键词"
            result = []
            for ch in novel.chapters:
                fields = [ch.title, ch.summary, ch.label]
                if any(keyword in f for f in fields):
                    status_label = _STATUS_LABELS.get(ch.status, ch.status)
                    display = chapter_display(ch)
                    result.append(
                        f"- {display} {ch.title}(ID:{ch.id}) [{status_label}]"
                    )
            return "\n".join(result) if result else f"未找到包含「{keyword}」的章节"
        elif action == "list":
            if not novel.chapters:
                return "暂无章节"
            result = []
            for ch in novel.chapters:
                status_label = _STATUS_LABELS.get(ch.status, ch.status)
                summary_info = f" | 摘要: {ch.summary[:40]}" if ch.summary else ""
                display = chapter_display(ch)
                extra_tag = " [番外]" if ch.is_extra else ""
                result.append(
                    f"- {display} {ch.title}(ID:{ch.id}, order={ch.order}) [{status_label}]{extra_tag}{summary_info}"
                )
            return "\n".join(result)
        elif action == "reorder":
            chapter_ids = kwargs.get("chapter_ids", [])
            if not chapter_ids:
                return "错误：chapter_ids不能为空。"
            if len(chapter_ids) != len(novel.chapters):
                return f"错误：传入了{len(chapter_ids)}个ID，但当前有{len(novel.chapters)}个章节，数量必须一致。"
            existing_ids = {ch.id for ch in novel.chapters}
            for cid in chapter_ids:
                if cid not in existing_ids:
                    return f"错误：章节ID {cid} 不存在。"
            id_to_ch = {ch.id: ch for ch in novel.chapters}
            novel.chapters = []
            for idx, cid in enumerate(chapter_ids):
                ch = id_to_ch[cid]
                ch.order = idx + 1.0
                novel.chapters.append(ch)
            await self._save(novel)
            # Return the reordered list for confirmation
            reordered = []
            for ch in novel.chapters:
                display = chapter_display(ch)
                reordered.append(f"  {ch.order:.0f}. {display} {ch.title}(ID:{ch.id})")
            return f"章节顺序已重排，共{len(novel.chapters)}章：\n" + "\n".join(reordered)
        elif action == "move":
            cid = kwargs.get("chapter_id", "")
            before_id = kwargs.get("before_chapter_id", "")
            after_id = kwargs.get("after_chapter_id", "")
            if not cid:
                return "错误：chapter_id不能为空。"
            if not before_id and not after_id:
                return "错误：必须指定 before_chapter_id 或 after_chapter_id。"
            if before_id and after_id:
                return "错误：before_chapter_id 和 after_chapter_id 只能指定一个。"
            # Find target chapter
            target = None
            for ch in novel.chapters:
                if ch.id == cid:
                    target = ch
                    break
            if target is None:
                return f"未找到ID为 {cid} 的章节"
            # Sort chapters by order for neighbor lookup
            novel.chapters.sort(key=lambda x: x.order)
            anchor_id = before_id or after_id
            if cid == anchor_id:
                return "错误：不能将章节移动到自身位置。"
            # Find anchor index
            anchor_idx = None
            for i, ch in enumerate(novel.chapters):
                if ch.id == anchor_id:
                    anchor_idx = i
                    break
            if anchor_idx is None:
                return f"未找到锚点章节ID {anchor_id}"
            if before_id:
                # Move target before anchor
                # New order = midpoint between prev and anchor
                if anchor_idx == 0:
                    new_order = novel.chapters[0].order - 1.0
                else:
                    prev_order = novel.chapters[anchor_idx - 1].order
                    # Skip target itself if it's the prev
                    if novel.chapters[anchor_idx - 1].id == cid and anchor_idx >= 2:
                        prev_order = novel.chapters[anchor_idx - 2].order
                    elif novel.chapters[anchor_idx - 1].id == cid:
                        prev_order = novel.chapters[anchor_idx].order - 2.0
                    new_order = (prev_order + novel.chapters[anchor_idx].order) / 2.0
            else:
                # Move target after anchor
                if anchor_idx == len(novel.chapters) - 1:
                    new_order = novel.chapters[-1].order + 1.0
                else:
                    next_order = novel.chapters[anchor_idx + 1].order
                    # Skip target itself if it's the next
                    if novel.chapters[anchor_idx + 1].id == cid and anchor_idx + 2 < len(novel.chapters):
                        next_order = novel.chapters[anchor_idx + 2].order
                    elif novel.chapters[anchor_idx + 1].id == cid:
                        next_order = novel.chapters[anchor_idx].order + 2.0
                    new_order = (novel.chapters[anchor_idx].order + next_order) / 2.0
            target.order = new_order
            novel.chapters.sort(key=lambda x: x.order)
            await self._save(novel)
            display = chapter_display(target)
            id_to_ch = {ch.id: ch for ch in novel.chapters}
            direction = f"移到{chapter_display(id_to_ch[anchor_id])}之前" if before_id else f"移到{chapter_display(id_to_ch[anchor_id])}之后"
            return f"{display}「{target.title}」已{direction}（order={new_order}）"
        elif action == "renumber":
            novel.chapters.sort(key=lambda x: x.order)
            next_num = 1
            changed = []
            for ch in novel.chapters:
                if ch.label or ch.is_extra:
                    continue
                old_num = ch.number
                ch.number = next_num
                if old_num != next_num:
                    changed.append(f"  {chapter_display(ch)} {ch.title}（{old_num} → {next_num}）")
                next_num += 1
            await self._save(novel)
            if not changed:
                return f"章节编号已连续，无需调整（共 {next_num - 1} 个普通章节）。"
            return f"已重编号 {len(changed)} 个章节：\n" + "\n".join(changed)
        return "未知操作"


@dataclass
class WorldSettingTool(BaseNovelTool):
    name: str = "manage_world_setting"
    description: str = "管理小说的世界观设定。支持创建、查询、修改、删除、列出和搜索世界观设定，包括时代背景、地理、魔法体系、社会结构等。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：create(创建), query(按ID查询), update(修改), delete(删除), list(列出所有), search(按分类/名称/描述模糊搜索)",
                    "enum": ["create", "query", "update", "delete", "list", "search"],
                },
                "setting_id": {
                    "type": "string",
                    "description": "设定ID。query/update/delete 时必填。",
                },
                "category": {
                    "type": "string",
                    "description": "设定分类。常见：时代、地理、政治、经济、军事、魔法体系、科技水平、社会结构、种族、宗教、文化等，也可自定义。create/update 时可选。",
                },
                "name": {
                    "type": "string",
                    "description": "设定名称。create 时必填，update 时可选。",
                },
                "description": {
                    "type": "string",
                    "description": "设定详细描述。create/update 时可选。",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，search 时必填。在分类、名称、描述中模糊匹配。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        novel, err = await self._get_novel(context)
        if err:
            return err
        action = kwargs.get("action", "")
        if action == "create":
            ws = WorldSetting(
                category=kwargs.get("category", ""),
                name=kwargs.get("name", ""),
                description=kwargs.get("description", ""),
            )
            novel.world_settings.append(ws)
            await self._save(novel)
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
                    ws.apply_updates(self._editable_kwargs(WorldSetting, kwargs))
                    await self._save(novel)
                    return f"世界观设定「{ws.name}」已更新"
            return f"未找到ID为 {sid} 的世界观设定"
        elif action == "delete":
            sid = kwargs.get("setting_id", "")
            before = len(novel.world_settings)
            novel.world_settings = [ws for ws in novel.world_settings if ws.id != sid]
            if len(novel.world_settings) < before:
                await self._save(novel)
                return "世界观设定已删除"
            return f"未找到ID为 {sid} 的世界观设定"
        elif action == "search":
            keyword = kwargs.get("keyword", "")
            if not keyword:
                return "请提供搜索关键词"
            result = []
            for ws in novel.world_settings:
                fields = [ws.category, ws.name, ws.description]
                if any(keyword in f for f in fields):
                    result.append(
                        f"- [{ws.category}] {ws.name}(ID:{ws.id}): {ws.description[:80] if ws.description else '无描述'}"
                    )
            return "\n".join(result) if result else f"未找到包含「{keyword}」的世界观设定"
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


@dataclass
class NovelTool(BaseNovelTool):
    name: str = "manage_novel"
    description: str = (
        "管理小说的全局信息。\n"
        "\n"
        "## update_synopsis\n"
        "更新全书故事梗概（synopsis）。应包含：当前故事进展、未解决的冲突、各角色当前状态（300-500字）。\n"
        "每次完成重要情节推进（如写完一章、角色关系发生重大变化、新伏笔埋下）后都应更新，"
        "以确保后续创作保持连贯，避免前后矛盾。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：update_synopsis(更新全书故事梗概)",
                    "enum": ["update_synopsis"],
                },
                "synopsis": {
                    "type": "string",
                    "description": "全书故事梗概（300-500字）。应包含：当前故事进展、未解决的冲突、各主要角色当前状态。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        novel, err = await self._get_novel(context)
        if err:
            return err
        action = kwargs.get("action", "")
        if action == "update_synopsis":
            synopsis = kwargs.get("synopsis", "")
            if not synopsis:
                return "错误：synopsis不能为空。"
            novel.synopsis = synopsis
            await self._save(novel)
            return f"故事梗概已更新（{len(synopsis)}字）"
        return "未知操作"


NOVEL_TOOLS = [CharacterTool, RelationshipTool, EventTool, OutlineTool, ChapterTool, WorldSettingTool, NovelTool]

_READONLY_ACTIONS = ["query", "list", "search"]
_READONLY_ACTION_DESC = "操作类型：query(按ID查询), list(列出所有), search(按名称/描述模糊搜索)"


def _make_readonly_cls(cls: type[BaseNovelTool]) -> type[BaseNovelTool]:
    """Return a subclass with parameters patched to only expose read-only actions and params."""
    params = cls.__dataclass_fields__["parameters"].default_factory().copy()
    props = params["properties"].copy()
    action = props["action"].copy()
    action["enum"] = _READONLY_ACTIONS
    action["description"] = _READONLY_ACTION_DESC
    props["action"] = action

    # Strip write-only parameters — keep only action, *_id, keyword, chapter_ids
    read_only_param_names = {"action"}
    for pname, pval in props.items():
        if pname == "action":
            continue
        if pname.endswith("_id") or pname == "keyword" or pname == "chapter_ids":
            read_only_param_names.add(pname)
    props = {k: v for k, v in props.items() if k in read_only_param_names}
    params["properties"] = props

    original_desc = cls.__dataclass_fields__["description"].default
    if original_desc.startswith("管理小说中的"):
        readonly_desc = "查询小说中的" + original_desc[len("管理小说中的"):]
    elif original_desc.startswith("管理小说的"):
        readonly_desc = "查询小说的" + original_desc[len("管理小说的"):]
    elif original_desc.startswith("管理"):
        readonly_desc = "查询" + original_desc[len("管理"):]
    else:
        readonly_desc = "查询" + original_desc

    return type(
        cls.__name__ + "Readonly",
        (cls,),
        {"parameters": params, "description": readonly_desc},
    )


READONLY_NOVEL_TOOLS = [
    _make_readonly_cls(t) for t in NOVEL_TOOLS
    if t is not NovelTool
]


def make_readonly_tools() -> list[type[BaseNovelTool]]:
    return READONLY_NOVEL_TOOLS
