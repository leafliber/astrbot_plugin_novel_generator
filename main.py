from __future__ import annotations

import asyncio
import base64
import dataclasses
import random
import re
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.agent.tool import ToolSet
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from quart import jsonify, request

import astrbot.api.message_components as Comp

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
from .tools import NOVEL_TOOLS, make_readonly_tools

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
        if await self.storage.find_novel_summary_by_name(name):
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
        summary = await self.storage.find_novel_summary_by_name(name)
        if summary is None:
            yield event.plain_result(f"未找到名为「{name}」的小说。")
            return
        await self.storage.set_active_novel(session_id, summary["id"])
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
        summary = await self.storage.find_novel_summary_by_name(name)
        if summary is None:
            yield event.plain_result(f"未找到名为「{name}」的小说。")
            return
        target_id = summary["id"]
        active_novel_id = await self.storage._get_active_novel_id(session_id)
        if active_novel_id and active_novel_id == target_id:
            await self.storage.remove_active_novel(session_id)
        await self.storage.delete_novel(target_id)
        yield event.plain_result(f"小说「{name}」已删除。")

    _SYSTEM_PROMPT = """\
你是一位专业的小说创作助手，负责使用工具来管理和创作小说的结构化数据。

## 创作流程
1. 收到创作要求后，先审视当前小说数据（角色、关系、大纲、世界观等），理解已有设定
2. 如需了解某个角色/事件/大纲的完整信息，先用 query 操作获取详细数据（context_info 中的内容是摘要，可能被截断）
3. 按需创建或更新角色、关系、世界观设定、事件等基础数据
4. 规划或更新剧情大纲，明确章节走向
5. 按大纲创作当前章节正文

## 写作质量要求
- 展示而非叙述（show, don't tell）：通过行动、对话和细节展现角色性格和情感，而非直接陈述
- 对话应体现角色个性：不同角色的说话方式、用词习惯应有区别
- 场景描写调动感官：视觉、听觉、触觉、嗅觉等，让读者身临其境
- 节奏控制：紧张场景用短句和快节奏，抒情和描写场景可舒缓
- 伏笔与呼应：前期埋下的线索应在后续章节有合理的回收
- 角色行为一致性：角色在正文中的行为应与其性格设定保持一致

## 章节正文写入（关键）
章节正文较长，必须分段写入，否则会因参数长度限制导致内容丢失：
- 用 manage_chapter 的 create 创建章节，content 留空或只写开头段落
- 用 append_content 分段追加正文，每次约 500-800 字，写完一个完整的叙事段落或场景
- 用 update 修改标题、状态、摘要等元数据（update 不会修改 content）
- 切勿在单次工具调用中传入完整长篇正文

## 修改已有内容
- 修改章节正文时：如需大幅修改，建议删除后重建；如需小幅度补充，使用 append_content 追加
- 修改角色/事件等设定时：用 update 操作更新对应字段
- 修改多章节时：逐章处理，每章修改完再处理下一章
- 删除角色后：系统会自动清理其关系和事件引用，但需手动检查大纲描述中是否有该角色的引用需要更新

## 数据引用规则
- 角色在关系和事件中以 ID 引用，创建角色后会返回 ID，list 也会显示 ID
- 创建关系或事件时，角色参数可传姓名或 ID，系统会自动解析
- 可用 search 操作按名称模糊搜索角色或事件，快速定位目标
- 删除角色时，其相关关系和事件引用会自动清理

## 数据一致性
- 修改角色信息后，检查是否需要同步更新关系描述或事件描述
- 新增角色后，考虑是否需要建立与其他角色的关系
- 创作正文时，确保角色行为与性格设定一致，事件发展与大纲走向一致
"""

    _READONLY_SYSTEM_PROMPT = """\
你是一位专业的小说阅读助手，负责回答用户关于小说内容的问题。

## 回答原则
1. 基于小说已有数据回答问题，如需了解某个角色/事件/大纲/章节的完整信息，先用工具获取详细数据
2. 你只能查询和搜索数据，不能创建、修改或删除任何内容
3. 回答时引用具体的角色、事件、章节等数据，让回答有据可依
4. 如果用户的问题涉及创作建议或修改要求，请告知用户使用 /novel write 命令"""

    async def _run_agent(
        self, event: AstrMessageEvent, novel: Novel, prompt: str, *, system_prompt: str | None = None
    ):
        umo = event.unified_msg_origin
        prov_id = self.config.get("provider_id", "") or await self.context.get_current_chat_provider_id(umo=umo)
        tools = ToolSet([t(storage=self.storage) for t in NOVEL_TOOLS])
        resolved_system_prompt = system_prompt if system_prompt is not None else None
        if resolved_system_prompt is None:
            custom_prompt = self.config.get("novel_system_prompt", "")
            resolved_system_prompt = custom_prompt if custom_prompt else self._SYSTEM_PROMPT
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

    async def _run_readonly_agent(
        self, event: AstrMessageEvent, novel: Novel, prompt: str
    ):
        umo = event.unified_msg_origin
        prov_id = self.config.get("provider_id", "") or await self.context.get_current_chat_provider_id(umo=umo)
        tools = ToolSet([t(storage=self.storage) for t in make_readonly_tools()])
        max_steps = self.config.get("max_agent_steps", 30)
        timeout = self.config.get("tool_call_timeout", 60)
        return await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=prompt,
            system_prompt=self._READONLY_SYSTEM_PROMPT,
            tools=tools,
            max_steps=max_steps,
            tool_call_timeout=timeout,
        )

    @novel.command("write")
    async def novel_write(self, event: AstrMessageEvent, *, requirement: str):
        """创作或修改小说，传入创作/修改要求"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        context_info = self._build_context_info(novel)
        prompt = f"{context_info}\n用户要求：{requirement}\n请根据要求进行创作或修改，使用工具来创建新内容或更新已有数据。"
        llm_resp = await self._run_agent(event, novel, prompt)
        async for result in self._yield_segmented(event, llm_resp.completion_text):
            yield result

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
        llm_resp = await self._run_readonly_agent(event, novel, prompt)
        async for result in self._yield_segmented(event, llm_resp.completion_text):
            yield result

    @staticmethod
    def _build_context_info(novel: Novel) -> str:
        max_field = 150
        max_total = 5000
        parts = [f"当前小说：「{novel.name}」"]

        if novel.characters:
            char_lines = []
            for c in novel.characters:
                char_lines.append(f"  • {c.name}(ID:{c.id}): {c.personality[:max_field] if c.personality else '无性格描述'}")
            parts.append(f"角色（{len(novel.characters)}个）：\n" + "\n".join(char_lines))

        if novel.relationships:
            rel_lines = []
            for r in novel.relationships:
                name_a = novel.character_name_by_id(r.character_a)
                name_b = novel.character_name_by_id(r.character_b)
                rel_lines.append(f"  • {name_a} ↔ {name_b}(ID:{r.id}) [{r.relation_type}]")
            parts.append(f"关系（{len(novel.relationships)}条）：\n" + "\n".join(rel_lines))

        if novel.outlines:
            out_lines = []
            for o in novel.outlines:
                out_lines.append(f"  • {o.title}: 走向={o.plot_direction[:max_field] if o.plot_direction else '无'}")
            parts.append(f"大纲（{len(novel.outlines)}条）：\n" + "\n".join(out_lines))

        if novel.world_settings:
            ws_lines = []
            for ws in novel.world_settings:
                ws_lines.append(f"  • [{ws.category}] {ws.name}: {ws.description[:max_field] if ws.description else '无描述'}")
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
                preview = ch.content[:120] + "..." if len(ch.content) > 120 else ch.content
                ch_lines.append(f"  第{ch.number}章 {ch.title}: {preview if preview else '（空）'}")
            parts.append(f"章节（{len(novel.chapters)}章）：\n" + "\n".join(ch_lines))
        else:
            parts.append("章节：暂无")

        result = "\n".join(parts) + "\n"
        if len(result) > max_total:
            result = result[:max_total] + "\n...（内容过长已截断，请使用工具查询完整数据）\n"
        return result

    @staticmethod
    def _split_text(text: str, max_length: int = 2000, header: str | None = None) -> list[str]:
        """Split text into segments respecting paragraph and sentence boundaries."""
        effective_max = max_length - (len(header) + 2 if header else 0)
        if effective_max <= 0 or len(text) <= effective_max:
            full = f"{header}\n\n{text}" if header else text
            return [full]

        # Pass 1: split on paragraph boundaries, greedily merge
        paragraphs = text.split("\n\n")
        raw_segments: list[str] = []
        current = ""
        for para in paragraphs:
            if not current:
                current = para
            elif len(current) + 2 + len(para) <= effective_max:
                current += "\n\n" + para
            else:
                raw_segments.append(current)
                current = para
        if current:
            raw_segments.append(current)

        # Pass 2: split oversized segments by sentence boundaries
        sentence_pat = re.compile(r".*?[。！？…~”」）\n]+|.+$")
        final_segments: list[str] = []
        for seg in raw_segments:
            if len(seg) <= effective_max:
                final_segments.append(seg)
                continue
            sentences = [s for s in sentence_pat.findall(seg) if s.strip()]
            if not sentences:
                final_segments.append(seg)
                continue
            sub = ""
            for s in sentences:
                if not sub:
                    sub = s
                elif len(sub) + len(s) <= effective_max:
                    sub += s
                else:
                    final_segments.append(sub)
                    sub = s
            if sub:
                final_segments.append(sub)

        # Pass 3: hard-split anything still over the limit
        result: list[str] = []
        for seg in final_segments:
            if len(seg) <= effective_max:
                result.append(seg)
            else:
                for i in range(0, len(seg), effective_max):
                    result.append(seg[i : i + effective_max])

        # Prepend header to first segment
        if header and result:
            result[0] = f"{header}\n\n{result[0]}"
        return result

    async def _yield_segmented(self, event: AstrMessageEvent, text: str, *, header: str | None = None):
        """Yield text as one or more plain_result messages, splitting if configured."""
        max_length = self.config.get("segment_max_length", 2000)
        if max_length <= 0:
            yield event.plain_result(f"{header}\n\n{text}" if header else text)
            return

        segments = self._split_text(text, max_length, header)
        total = len(segments)
        delay = self.config.get("segment_delay", 5)

        for i, seg in enumerate(segments):
            if total > 1:
                seg = f"[{i + 1}/{total}] {seg}"
            yield event.plain_result(seg)
            if delay > 0 and i < total - 1:
                await asyncio.sleep(delay + random.uniform(0, 1))

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
                    async for result in self._yield_segmented(
                        event, ch.content, header=f"第{ch.number}章 {ch.title}"
                    ):
                        yield result
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
            async for result in self._yield_segmented(event, "\n".join(lines)):
                yield result

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

    @novel.command("download")
    async def novel_download(self, event: AstrMessageEvent, chapter_number: int = 0):
        """下载小说TXT文件，不指定章节号则下载全本"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        if not novel.chapters:
            yield event.plain_result("当前小说暂无章节，无法下载。")
            return

        if chapter_number > 0:
            target_ch = None
            for ch in novel.chapters:
                if ch.number == chapter_number:
                    target_ch = ch
                    break
            if target_ch is None:
                yield event.plain_result(f"未找到第{chapter_number}章。")
                return
            if not target_ch.content:
                yield event.plain_result(f"第{chapter_number}章「{target_ch.title}」暂无内容。")
                return
            filename = f"{novel.name}_第{target_ch.number}章_{target_ch.title}.txt"
            content = f"{novel.name}\n第{target_ch.number}章 {target_ch.title}\n\n{target_ch.content}"
        else:
            parts = [novel.name, "=" * len(novel.name)]
            for ch in novel.chapters:
                parts.append(f"\n第{ch.number}章 {ch.title}\n")
                if ch.content:
                    parts.append(ch.content)
                else:
                    parts.append("（本章暂无内容）")
                parts.append("")
            content = "\n".join(parts)
            filename = f"{novel.name}_全本.txt"

        safe_filename = filename.replace("/", "_").replace("\\", "_")
        b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        chain = [Comp.File(file=f"base64://{b64}", name=safe_filename)]
        yield event.chain_result(chain)

    def _register_web_apis(self):
        prefix = f"/{PLUGIN_NAME}"
        self.context.register_web_api(
            f"{prefix}/novels", self.api_list_novels, ["GET"], "List all novels"
        )
        self.context.register_web_api(
            f"{prefix}/novels/<novel_id>",
            self.api_get_novel,
            ["GET"],
            "Get novel detail",
        )
        for collection_name, cfg in _CRUD_CONFIG.items():
            self.context.register_web_api(
                f"{prefix}/novels/<novel_id>/{collection_name}",
                self._make_crud_list_handler(collection_name, cfg),
                ["GET", "POST"],
                f"{collection_name.capitalize()} CRUD",
            )
            self.context.register_web_api(
                f"{prefix}/novels/<novel_id>/{collection_name}/<item_id>",
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
                return jsonify([dataclasses.asdict(item) for item in items])
            elif request.method == "POST":
                data = await request.get_json() or {}
                kwargs = {f: data.get(f, "" if f != "involved_characters" else []) for f in create_fields}
                if "number" in kwargs and kwargs["number"] == "":
                    kwargs["number"] = max((item.number for item in items), default=0) + 1
                item = model_cls(**kwargs)
                items.append(item)
                if sort_after_create:
                    items.sort(key=lambda x: x.number)
                await self.storage.save_novel(novel)
                return jsonify(dataclasses.asdict(item))

        return handler

    def _make_crud_item_handler(self, collection_name: str, cfg: dict):
        sort_after_update = cfg.get("sort_after_create", False)

        async def handler(novel_id, item_id):
            novel = await self.storage.load_novel(novel_id)
            if novel is None:
                return jsonify({"error": "Novel not found"}), 404
            items = getattr(novel, collection_name)
            data = await request.get_json() or {}
            if data.get("_action") == "delete":
                setattr(novel, collection_name, [i for i in items if i.id != item_id])
                if collection_name == "characters":
                    novel.relationships = [
                        r for r in novel.relationships
                        if r.character_a != item_id and r.character_b != item_id
                    ]
                    for e in novel.events:
                        e.involved_characters = [
                            c for c in e.involved_characters if c != item_id
                        ]
                await self.storage.save_novel(novel)
                return jsonify({"success": True})
            else:
                for item in items:
                    if item.id == item_id:
                        item.apply_updates(data)
                        if sort_after_update:
                            items.sort(key=lambda x: x.number)
                        await self.storage.save_novel(novel)
                        return jsonify(dataclasses.asdict(item))
                return jsonify({"error": f"{collection_name.rstrip('s').capitalize()} not found"}), 404

        return handler
