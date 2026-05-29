from __future__ import annotations

from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.agent.tool import ToolSet
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from quart import jsonify, request

from .models import (
    Character,
    Chapter,
    Event,
    Novel,
    Outline,
    Relationship,
    WorldSetting,
)
from .storage import PLUGIN_NAME, NovelStorage
from .tools import NOVEL_TOOLS

_CRUD_CONFIG: dict[str, dict[str, Any]] = {
    "characters": {
        "model": Character,
        "create_fields": ["name", "personality", "appearance", "background", "notes"],
        "sort_after_create": False,
    },
    "relationships": {
        "model": Relationship,
        "create_fields": ["character_a", "character_b", "relation_type", "description"],
        "sort_after_create": False,
    },
    "events": {
        "model": Event,
        "create_fields": ["name", "timeline_position", "description", "involved_characters"],
        "sort_after_create": False,
    },
    "outlines": {
        "model": Outline,
        "create_fields": ["title", "chapter_plan", "plot_direction", "notes", "parent_id", "order"],
        "sort_after_create": False,
    },
    "chapters": {
        "model": Chapter,
        "create_fields": ["number", "title", "content", "status", "summary"],
        "sort_after_create": True,
    },
    "world_settings": {
        "model": WorldSetting,
        "create_fields": ["category", "name", "description"],
        "sort_after_create": False,
    },
}


class NovelGeneratorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        data_base_path = Path(get_astrbot_data_path())
        self.storage = NovelStorage(data_base_path)
        self.storage.set_kv_plugin(self)
        self._register_web_apis()

    async def terminate(self):
        pass

    def _get_session_id(self, event: AstrMessageEvent) -> str:
        return event.unified_msg_origin

    @filter.command_group("novel")
    def novel(self):
        pass

    @novel.command("create")
    async def novel_create(self, event: AstrMessageEvent, name: str):
        """创建一本新小说"""
        session_id = self._get_session_id(event)
        existing = await self.storage.list_novels()
        if any(n.name == name for n in existing):
            yield event.plain_result(f"已存在名为「{name}」的小说，请使用其他名称。")
            return
        novel = Novel(name=name)
        await self.storage.save_novel(novel)
        await self.storage.set_active_novel(session_id, novel.id)
        yield event.plain_result(
            f"小说「{name}」已创建并激活！使用 /novel write 开始创作。"
        )

    @novel.command("switch")
    async def novel_switch(self, event: AstrMessageEvent, name: str):
        """切换到指定小说"""
        session_id = self._get_session_id(event)
        novels = await self.storage.list_novels()
        target = None
        for n in novels:
            if n.name == name:
                target = n
                break
        if target is None:
            yield event.plain_result(f"未找到名为「{name}」的小说。")
            return
        await self.storage.set_active_novel(session_id, target.id)
        yield event.plain_result(f"已切换到小说「{name}」。")

    @novel.command("list")
    async def novel_list(self, event: AstrMessageEvent):
        """列出所有小说"""
        session_id = self._get_session_id(event)
        active_novel = await self.storage.get_active_novel(session_id)
        active_id = active_novel.id if active_novel else None
        novels = await self.storage.list_novels()
        if not novels:
            yield event.plain_result("暂无小说，使用 /novel create 创建一本吧！")
            return
        lines = ["📖 小说列表："]
        for n in novels:
            marker = " ✅ [当前]" if n.id == active_id else ""
            ch_count = len(n.chapters)
            lines.append(f"  • {n.name}（{ch_count} 章）{marker}")
        yield event.plain_result("\n".join(lines))

    @novel.command("delete")
    async def novel_delete(self, event: AstrMessageEvent, name: str):
        """删除指定小说"""
        session_id = self._get_session_id(event)
        novels = await self.storage.list_novels()
        target = None
        for n in novels:
            if n.name == name:
                target = n
                break
        if target is None:
            yield event.plain_result(f"未找到名为「{name}」的小说。")
            return
        active_novel = await self.storage.get_active_novel(session_id)
        if active_novel and active_novel.id == target.id:
            await self.storage.remove_active_novel(session_id)
        await self.storage.delete_novel(target.id)
        yield event.plain_result(f"小说「{name}」已删除。")

    async def _run_agent(
        self, event: AstrMessageEvent, novel: Novel, prompt: str, *, system_prompt: str | None = None
    ):
        umo = event.unified_msg_origin
        prov_id = self.config.get("provider_id", "") or await self.context.get_current_chat_provider_id(umo=umo)
        tools = ToolSet([t(storage=self.storage) for t in NOVEL_TOOLS])
        resolved_system_prompt = system_prompt if system_prompt is not None else self.config.get("novel_system_prompt", "")
        max_steps = self.config.get("max_agent_steps", 30)
        timeout = self.config.get("tool_call_timeout", 60)
        return await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=prompt,
            system_prompt=resolved_system_prompt,
            tools=tools,
            max_steps=max_steps,
            tool_call_timeout=timeout,
        )

    @novel.command("write")
    async def novel_write(self, event: AstrMessageEvent, *, requirement: str):
        """写故事，传入创作要求"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        context_info = self._build_context_info(novel)
        prompt = f"{context_info}\n用户创作要求：{requirement}"
        llm_resp = await self._run_agent(event, novel, prompt)
        yield event.plain_result(llm_resp.completion_text)

    @novel.command("revise")
    async def novel_revise(self, event: AstrMessageEvent, *, requirement: str):
        """修正故事，传入修正要求"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        context_info = self._build_context_info(novel)
        prompt = f"{context_info}\n用户修正要求：{requirement}\n请根据要求修改已有内容，使用工具来更新数据。"
        llm_resp = await self._run_agent(event, novel, prompt)
        yield event.plain_result(llm_resp.completion_text)

    @novel.command("ask")
    async def novel_ask(self, event: AstrMessageEvent, *, question: str):
        """对小说提问"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        context_info = self._build_context_info(novel)
        prompt = f"{context_info}\n用户问题：{question}\n请基于小说内容回答，如需查看详细数据请使用工具查询。"
        llm_resp = await self._run_agent(event, novel, prompt)
        yield event.plain_result(llm_resp.completion_text)

    @staticmethod
    def _build_context_info(novel: Novel) -> str:
        parts = [f"当前小说：「{novel.name}」"]

        if novel.characters:
            char_lines = []
            for c in novel.characters:
                char_lines.append(f"  • {c.name}(ID:{c.id}): {c.personality[:60] if c.personality else '无性格描述'}")
            parts.append(f"角色（{len(novel.characters)}个）：\n" + "\n".join(char_lines))

        if novel.relationships:
            rel_lines = []
            for r in novel.relationships:
                name_a = novel.character_name_by_id(r.character_a)
                name_b = novel.character_name_by_id(r.character_b)
                rel_lines.append(f"  • {name_a} ↔ {name_b}({r.relation_type})")
            parts.append(f"关系（{len(novel.relationships)}条）：\n" + "\n".join(rel_lines))

        if novel.outlines:
            out_lines = []
            for o in novel.outlines:
                out_lines.append(f"  • {o.title}: 走向={o.plot_direction[:60] if o.plot_direction else '无'}")
            parts.append(f"大纲（{len(novel.outlines)}条）：\n" + "\n".join(out_lines))

        if novel.world_settings:
            ws_lines = []
            for ws in novel.world_settings:
                ws_lines.append(f"  • [{ws.category}] {ws.name}: {ws.description[:60] if ws.description else '无描述'}")
            parts.append(f"世界观设定（{len(novel.world_settings)}条）：\n" + "\n".join(ws_lines))

        if novel.events:
            evt_lines = []
            for e in novel.events:
                char_names = [novel.character_name_by_id(c) for c in e.involved_characters]
                chars = ", ".join(char_names) if char_names else "无"
                evt_lines.append(f"  • {e.name}[{e.timeline_position}](涉及:{chars})")
            parts.append(f"事件（{len(novel.events)}个）：\n" + "\n".join(evt_lines))

        if novel.chapters:
            ch_lines = []
            for ch in novel.chapters:
                preview = ch.content[:80] + "..." if len(ch.content) > 80 else ch.content
                ch_lines.append(f"  第{ch.number}章 {ch.title}: {preview if preview else '（空）'}")
            parts.append(f"章节（{len(novel.chapters)}章）：\n" + "\n".join(ch_lines))
        else:
            parts.append("章节：暂无")

        return "\n".join(parts) + "\n"

    @novel.command("read")
    async def novel_read(self, event: AstrMessageEvent, chapter_number: int = 0):
        """阅读小说，可指定章节号"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        if chapter_number > 0:
            for ch in novel.chapters:
                if ch.number == chapter_number:
                    yield event.plain_result(
                        f"第{ch.number}章 {ch.title}\n\n{ch.content}"
                    )
                    return
            yield event.plain_result(f"未找到第{chapter_number}章。")
        else:
            lines = [f"📖 「{novel.name}」概览"]
            lines.append(f"角色：{len(novel.characters)} 个")
            lines.append(f"关系：{len(novel.relationships)} 条")
            lines.append(f"事件：{len(novel.events)} 个")
            lines.append(f"大纲：{len(novel.outlines)} 条")
            lines.append(f"世界观设定：{len(novel.world_settings)} 条")
            lines.append(f"章节：{len(novel.chapters)} 章")
            if novel.characters:
                lines.append("\n角色列表：")
                for c in novel.characters:
                    lines.append(
                        f"  • {c.name}: {c.personality[:30] if c.personality else '无描述'}"
                    )
            if novel.world_settings:
                lines.append("\n世界观设定：")
                for ws in novel.world_settings:
                    lines.append(f"  • [{ws.category}] {ws.name}")
            if novel.chapters:
                lines.append("\n章节目录：")
                for ch in novel.chapters:
                    lines.append(f"  第{ch.number}章 {ch.title}")
            yield event.plain_result("\n".join(lines))

    @novel.command("chapters")
    async def novel_chapters(self, event: AstrMessageEvent):
        """列出所有章节"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        if not novel.chapters:
            yield event.plain_result("当前小说暂无章节，使用 /novel write 开始创作吧！")
            return
        lines = [f"📚 「{novel.name}」章节列表："]
        for ch in novel.chapters:
            content_len = len(ch.content)
            lines.append(f"  第{ch.number}章 {ch.title}（{content_len}字）")
        yield event.plain_result("\n".join(lines))

    @novel.command("stop")
    async def novel_stop(self, event: AstrMessageEvent):
        """结束当前创作会话"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result("当前没有激活的小说。")
            return
        await self.storage.remove_active_novel(session_id)
        yield event.plain_result(
            f"小说「{novel.name}」的创作会话已结束，数据已保存。使用 /novel switch 可重新激活。"
        )

    def _register_web_apis(self):
        prefix = f"/{PLUGIN_NAME}"
        self.context.register_web_api(
            f"{prefix}/novels", self.api_list_novels, ["GET"], "List all novels"
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}",
            self.api_get_novel,
            ["GET"],
            "Get novel detail",
        )
        for collection_name, cfg in _CRUD_CONFIG.items():
            self.context.register_web_api(
                f"{prefix}/novels/{{novel_id}}/{collection_name}",
                self._make_crud_list_handler(collection_name, cfg),
                ["GET", "POST"],
                f"{collection_name.capitalize()} CRUD",
            )
            self.context.register_web_api(
                f"{prefix}/novels/{{novel_id}}/{collection_name}/{{item_id}}",
                self._make_crud_item_handler(collection_name, cfg),
                ["POST"],
                f"{collection_name.capitalize()} item CRUD",
            )

    async def api_list_novels(self):
        summaries = await self.storage.list_novel_summaries()
        return jsonify(summaries)

    async def api_get_novel(self, novel_id):
        novel = await self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        return jsonify(novel.to_dict())

    def _make_crud_list_handler(self, collection_name: str, cfg: dict):
        model_cls = cfg["model"]
        create_fields = cfg["create_fields"]
        sort_after_create = cfg["sort_after_create"]

        async def handler(novel_id):
            novel = await self.storage.load_novel(novel_id)
            if novel is None:
                return jsonify({"error": "Novel not found"}), 404
            items = getattr(novel, collection_name)
            if request.method == "GET":
                return jsonify([item.__dict__ for item in items])
            elif request.method == "POST":
                data = await request.get_json()
                kwargs = {f: data.get(f, "" if f != "involved_characters" else []) for f in create_fields}
                if "number" in kwargs and kwargs["number"] == "":
                    kwargs["number"] = len(items) + 1
                item = model_cls(**kwargs)
                items.append(item)
                if sort_after_create:
                    items.sort(key=lambda x: x.number)
                await self.storage.save_novel(novel)
                return jsonify(item.__dict__)

        return handler

    def _make_crud_item_handler(self, collection_name: str, cfg: dict):
        sort_after_update = cfg.get("sort_after_create", False)

        async def handler(novel_id, item_id):
            novel = await self.storage.load_novel(novel_id)
            if novel is None:
                return jsonify({"error": "Novel not found"}), 404
            items = getattr(novel, collection_name)
            data = await request.get_json()
            if data.get("_action") == "delete":
                setattr(novel, collection_name, [i for i in items if i.id != item_id])
                await self.storage.save_novel(novel)
                return jsonify({"success": True})
            else:
                for item in items:
                    if item.id == item_id:
                        item.apply_updates(data)
                        if sort_after_update:
                            items.sort(key=lambda x: x.number)
                        await self.storage.save_novel(novel)
                        return jsonify(item.__dict__)
                return jsonify({"error": f"{collection_name.rstrip('s').capitalize()} not found"}), 404

        return handler
