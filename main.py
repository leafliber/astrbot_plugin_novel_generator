from __future__ import annotations

import asyncio
import base64
import dataclasses
import os
import random
import re
import tempfile
import time
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
    chapter_display,
)
from .storage import PLUGIN_NAME, NovelStorage
from .tools import NOVEL_TOOLS, make_readonly_tools


def compute_session_id(event: AstrMessageEvent, mode: str) -> str:
    if mode == "user":
        return f"user:{event.message_obj.sender.user_id}"
    if mode == "none":
        return "_global"
    return event.unified_msg_origin

_CRUD_CONFIG: dict[str, dict[str, Any]] = {
    "characters": {
        "model": Character,
        "create_fields": ["name", "personality", "appearance", "background", "notes"],
        "sort_after_create": False,
        "needs_content": False,
    },
    "relationships": {
        "model": Relationship,
        "create_fields": ["character_a", "character_b", "relation_type", "description"],
        "sort_after_create": False,
        "needs_content": False,
    },
    "events": {
        "model": Event,
        "create_fields": ["name", "timeline_position", "description", "involved_characters"],
        "sort_after_create": False,
        "needs_content": False,
    },
    "outlines": {
        "model": Outline,
        "create_fields": ["title", "chapter_plan", "plot_direction", "notes", "parent_id", "order"],
        "sort_after_create": False,
        "needs_content": False,
    },
    "chapters": {
        "model": Chapter,
        "create_fields": ["number", "order", "title", "content", "status", "summary", "label", "is_extra"],
        "sort_after_create": True,
        "needs_content": False,
        "strip_content": True,
    },
    "world_settings": {
        "model": WorldSetting,
        "create_fields": ["category", "name", "description"],
        "sort_after_create": False,
        "needs_content": False,
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
        mode = self.config.get("session_isolation", "group")
        return compute_session_id(event, mode)

    def _get_novel_filter(self, event: AstrMessageEvent) -> dict:
        mode = self.config.get("session_isolation", "group")
        if mode == "user":
            return {"owner_user_id": event.message_obj.sender.user_id}
        if mode == "none":
            return {}
        group_id = event.message_obj.group_id
        if group_id:
            return {"owner_group_id": group_id}
        return {"owner_user_id": event.message_obj.sender.user_id}

    @filter.command_group("novel", alias={"小说"})
    def novel(self):
        pass

    @novel.command("create", alias={"创建"})
    async def novel_create(self, event: AstrMessageEvent, name: str):
        """创建一本新小说"""
        if not name.strip():
            yield event.plain_result("小说名称不能为空，请提供名称。")
            return
        session_id = self._get_session_id(event)
        novel_filter = self._get_novel_filter(event)
        if await self.storage.find_novel_summary_by_name(name, **novel_filter):
            yield event.plain_result(f"已存在名为「{name}」的小说，请使用其他名称。")
            return
        novel = Novel(
            name=name,
            owner_group_id=event.message_obj.group_id,
            owner_user_id=event.message_obj.sender.user_id,
        )
        await self.storage.save_novel(novel)
        await self.storage.set_active_novel(session_id, novel.id)
        yield event.plain_result(
            f"小说「{name}」已创建并激活！使用 /novel write 开始创作。"
        )

    @novel.command("switch", alias={"切换"})
    async def novel_switch(self, event: AstrMessageEvent, name: str):
        """切换到指定小说"""
        session_id = self._get_session_id(event)
        novel_filter = self._get_novel_filter(event)
        summary = await self.storage.find_novel_summary_by_name(name, **novel_filter)
        if summary is None:
            yield event.plain_result(f"未找到名为「{name}」的小说。")
            return
        await self.storage.set_active_novel(session_id, summary["id"])
        yield event.plain_result(f"已切换到小说「{name}」。")

    @novel.command("list", alias={"列表"})
    async def novel_list(self, event: AstrMessageEvent):
        """列出所有小说"""
        session_id = self._get_session_id(event)
        novel_filter = self._get_novel_filter(event)
        active_id = await self.storage.get_active_novel_id(session_id)
        summaries = await self.storage.list_novel_summaries(**novel_filter)
        if not summaries:
            yield event.plain_result("暂无小说，使用 /novel create 创建一本吧！")
            return
        lines = ["📖 小说列表："]
        for s in summaries:
            marker = " ✅ [当前]" if s.get("id") == active_id else ""
            ch_count = s.get("chapter_count", 0)
            lines.append(f"  • {s['name']}（{ch_count} 章）{marker}")
        yield event.plain_result("\n".join(lines))

    @novel.command("delete", alias={"删除"})
    async def novel_delete(self, event: AstrMessageEvent, name: str):
        """删除指定小说"""
        session_id = self._get_session_id(event)
        novel_filter = self._get_novel_filter(event)
        summary = await self.storage.find_novel_summary_by_name(name, **novel_filter)
        if summary is None:
            yield event.plain_result(f"未找到名为「{name}」的小说。")
            return
        target_id = summary["id"]
        active_novel_id = await self.storage.get_active_novel_id(session_id)
        if active_novel_id and active_novel_id == target_id:
            await self.storage.remove_active_novel(session_id)
        await self.storage.delete_novel(target_id)
        yield event.plain_result(f"小说「{name}」已删除。")

    @novel.command("transfer", alias={"转让"})
    async def novel_transfer(self, event: AstrMessageEvent, name: str):
        """转让小说所有权"""
        session_id = self._get_session_id(event)
        # Use user identity to find novels they personally own
        user_id = event.message_obj.sender.user_id
        summary = await self.storage.find_novel_summary_by_name(name, owner_user_id=user_id)
        if summary is None:
            yield event.plain_result(f"未找到名为「{name}」的小说。")
            return

        mode = self.config.get("session_isolation", "group")
        target_user_id = None
        for comp in event.message_obj.message:
            if hasattr(comp, "qq"):
                target_user_id = comp.qq
                break

        novel = await self.storage.load_novel(summary["id"], load_content=False)
        if novel is None:
            yield event.plain_result(f"小说「{name}」加载失败。")
            return

        if mode == "user":
            if not target_user_id:
                yield event.plain_result("用户隔离模式下需要 @mention 目标用户。")
                return
            novel.owner_user_id = target_user_id
            msg = f"小说「{name}」已转让。"
        else:
            group_id = event.message_obj.group_id
            if group_id:
                novel.owner_group_id = group_id
            else:
                novel.owner_user_id = event.message_obj.sender.user_id
            msg = f"小说「{name}」已转让到当前{'群聊' if group_id else '会话'}。"

        await self.storage.save_novel(novel)

        active_novel_id = await self.storage.get_active_novel_id(session_id)
        if active_novel_id and active_novel_id == novel.id:
            await self.storage.remove_active_novel(session_id)

        yield event.plain_result(msg)

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
- 用 append_content 分段追加正文，每次约 1500-2500 字，写完一个完整的叙事段落或场景
- 用 update 修改标题、状态、摘要等元数据（update 不会修改 content）
- 切勿在单次工具调用中传入完整长篇正文

## 章节排序与特殊章节
章节有两个独立的概念：
- number（章节号）：显示用标识，如 1、2、3。普通章节自动递增，不影响排序
- order（排序权重）：控制章节在列表中的实际位置，由系统自动管理

特殊章节（番外、序章、终章等）通过以下字段控制：
- label：自定义显示标签，设置后覆盖默认的"第N章"格式（如"番外一·前传"、"序章"）
- is_extra：番外标记。若 is_extra=true 且无 label，自动显示为"番外·标题"
- 所有字段（label、is_extra、number、order）均可通过 update 随时修改

调整章节顺序：
- 少量调整（移动单个章节）：使用 move 动作，指定 before_chapter_id 或 after_chapter_id
- 整体重排（批量调整多个章节）：使用 reorder 动作，传入完整的章节ID列表

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

## 章节摘要维护
- 每完成一章正文后，务必用 manage_chapter 的 update 填写该章 summary（100-200字，概括关键情节、角色状态变化、伏笔线索）
- summary 是后续章节创作的重要参考，会自动展示在上下文中

## 故事梗概维护
- 每次完成重要情节推进（如写完一章、角色关系发生重大变化、新伏笔埋下），使用 manage_novel 的 update_synopsis 更新故事梗概
- synopsis 应包含：当前故事进展、未解决的冲突、各角色当前状态（300-500字）
- 这能确保后续创作保持连贯，避免前后矛盾

## 创作前回顾
- 审阅 synopsis（故事梗概）了解整体进展
- 如果需要回顾具体章节内容，用 manage_chapter 的 query 读取最近 1-2 章的完整正文
- 特别注意：检查角色当前状态是否与之前章节一致，伏笔是否在后续得到合理回收
"""

    _WRITE_HINTS = [
        "正在创作中，请稍候...",
        "灵感涌现中，请稍候...",
        "笔墨正在挥洒...",
        "故事正在展开...",
        "构思中，请稍候...",
        "正在伏案疾书...",
    ]

    _ASK_HINTS = [
        "正在思考，请稍候...",
        "翻阅书页中...",
        "正在回忆故事细节...",
    ]

    _READONLY_SYSTEM_PROMPT = """\
你是一位专业的小说阅读助手，负责回答用户关于小说内容的问题。

## 回答原则
1. 基于小说已有数据回答问题，如需了解某个角色/事件/大纲/章节的完整信息，先用工具获取详细数据
2. 你只能查询和搜索数据，不能创建、修改或删除任何内容
3. 回答时引用具体的角色、事件、章节等数据，让回答有据可依
4. 如果用户的问题涉及创作建议或修改要求，请告知用户使用 /novel write 命令"""

    async def _run_agent(
        self,
        event: AstrMessageEvent,
        novel: Novel,
        prompt: str,
        *,
        system_prompt: str | None = None,
        tools: ToolSet | None = None,
    ):
        umo = event.unified_msg_origin
        prov_id = self.config.get("provider_id", "") or await self.context.get_current_chat_provider_id(umo=umo)
        session_id = self._get_session_id(event)
        if tools is None:
            tools = ToolSet([t(storage=self.storage, session_id=session_id) for t in NOVEL_TOOLS])
        if system_prompt is None:
            custom_prompt = self.config.get("novel_system_prompt", "")
            system_prompt = custom_prompt if custom_prompt else self._SYSTEM_PROMPT
        max_steps = self.config.get("max_agent_steps", 30)
        timeout = self.config.get("tool_call_timeout", 60)
        return await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=prompt,
            system_prompt=system_prompt,
            tools=tools,
            max_steps=max_steps,
            tool_call_timeout=timeout,
        )

    async def _run_readonly_agent(
        self, event: AstrMessageEvent, novel: Novel, prompt: str
    ):
        session_id = self._get_session_id(event)
        tools = ToolSet([t(storage=self.storage, session_id=session_id) for t in make_readonly_tools()])
        return await self._run_agent(
            event, novel, prompt,
            system_prompt=self._READONLY_SYSTEM_PROMPT,
            tools=tools,
        )

    @novel.command("write", alias={"写"})
    async def novel_write(self, event: AstrMessageEvent, *, requirement: str):
        """创作或修改小说，传入创作/修改要求"""
        if not requirement.strip():
            yield event.plain_result("创作要求不能为空，请描述你想要的内容。")
            return
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        context_info = self._build_context_info(novel)
        prompt = f"{context_info}\n用户要求：{requirement}\n请根据要求进行创作或修改，使用工具来创建新内容或更新已有数据。"
        # Auto-inject recent chapter context for continuity
        if novel.chapters:
            recent = []
            for ch in sorted(novel.chapters, key=lambda x: x.order)[-2:]:
                text = ch.summary or ch.content[:500]
                if text:
                    recent.append(f"  {chapter_display(ch)} {ch.title}: {text}")
            if recent:
                prompt += "\n\n最近章节回顾：\n" + "\n".join(recent)
        yield event.plain_result(random.choice(self._WRITE_HINTS))
        llm_resp = await self._run_agent(event, novel, prompt)
        async for result in self._yield_segmented(event, llm_resp.completion_text):
            yield result

    @novel.command("ask", alias={"问"})
    async def novel_ask(self, event: AstrMessageEvent, *, question: str):
        """对小说提问"""
        if not question.strip():
            yield event.plain_result("问题不能为空，请输入你的问题。")
            return
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        context_info = self._build_context_info(novel)
        prompt = f"{context_info}\n用户问题：{question}\n请基于小说内容回答，如需查看详细数据请使用工具查询。"
        yield event.plain_result(random.choice(self._ASK_HINTS))
        llm_resp = await self._run_readonly_agent(event, novel, prompt)
        async for result in self._yield_segmented(event, llm_resp.completion_text):
            yield result

    @staticmethod
    def _build_context_info(novel: Novel) -> str:
        max_field = 300
        max_total = 8000

        def _truncate(text: str, limit: int) -> str:
            return text[:limit] + "…" if len(text) > limit else text

        # Build sections in priority order; chapters and synopsis are most important.
        sections: list[tuple[str, int]] = []  # (text, min_budget)
        header = f"当前小说：「{novel.name}」"
        used = len(header) + 1  # +1 for the \n join

        if novel.synopsis:
            sections.append((f"故事梗概：{novel.synopsis}", 0))

        if novel.chapters:
            sorted_chapters = sorted(novel.chapters, key=lambda x: x.order)
            ch_lines = []
            for ch in sorted_chapters:
                if ch.summary:
                    ch_lines.append(f"  {chapter_display(ch)} {ch.title}: {ch.summary}")
                elif ch.content:
                    ch_lines.append(f"  {chapter_display(ch)} {ch.title}: {_truncate(ch.content, 120)}...")
                else:
                    ch_lines.append(f"  {chapter_display(ch)} {ch.title}: （空）")
            sections.append((f"章节（{len(sorted_chapters)}章）：\n" + "\n".join(ch_lines), 50))

        if novel.characters:
            char_lines = []
            for c in novel.characters:
                bg = f" | 背景: {_truncate(c.background, max_field)}" if c.background else ""
                char_lines.append(f"  • {c.name}(ID:{c.id}): {_truncate(c.personality, max_field) if c.personality else '无性格描述'}{bg}")
            sections.append((f"角色（{len(novel.characters)}个）：\n" + "\n".join(char_lines), 0))

        if novel.relationships:
            rel_lines = []
            for r in novel.relationships:
                name_a = novel.character_name_by_id(r.character_a)
                name_b = novel.character_name_by_id(r.character_b)
                desc = f": {_truncate(r.description, max_field)}" if r.description else ""
                rel_lines.append(f"  • {name_a} ↔ {name_b}(ID:{r.id}) [{r.relation_type}]{desc}")
            sections.append((f"关系（{len(novel.relationships)}条）：\n" + "\n".join(rel_lines), 0))

        if novel.outlines:
            out_lines = []
            for o in novel.outlines:
                plan = f" | 规划: {_truncate(o.chapter_plan, max_field)}" if o.chapter_plan else ""
                out_lines.append(f"  • {o.title}: 走向={_truncate(o.plot_direction, max_field) if o.plot_direction else '无'}{plan}")
            sections.append((f"大纲（{len(novel.outlines)}条）：\n" + "\n".join(out_lines), 0))

        if novel.world_settings:
            ws_lines = []
            for ws in novel.world_settings:
                ws_lines.append(f"  • [{ws.category}] {ws.name}: {_truncate(ws.description, max_field) if ws.description else '无描述'}")
            sections.append((f"世界观设定（{len(novel.world_settings)}条）：\n" + "\n".join(ws_lines), 0))

        if novel.events:
            evt_lines = []
            for e in novel.events:
                char_names = [novel.character_name_by_id(c) for c in e.involved_characters]
                chars = ", ".join(char_names) if char_names else "无"
                desc = f": {_truncate(e.description, max_field)}" if e.description else ""
                evt_lines.append(f"  • {e.name}[{e.timeline_position}](涉及:{chars}){desc}")
            sections.append((f"事件（{len(novel.events)}个）：\n" + "\n".join(evt_lines), 0))

        # Allocate remaining budget across sections, respecting min_budget
        remaining = max_total - used
        result_parts = [header]
        suffix_min = [0] * (len(sections) + 1)
        for i in range(len(sections) - 1, -1, -1):
            suffix_min[i] = suffix_min[i + 1] + sections[i][1]
        for idx, (text, min_budget) in enumerate(sections):
            budget = max(min_budget, remaining - suffix_min[idx + 1])
            budget = max(budget, 0)
            if len(text) <= budget:
                result_parts.append(text)
                remaining -= len(text) + 1
            elif budget > 50:
                result_parts.append(text[:budget] + "\n…（已截断，请使用工具查询完整数据）")
                remaining = 0
            # else: skip section entirely when budget is too small
        return "\n".join(result_parts) + "\n"

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
        sentence_pat = re.compile(r".*?[。！？…~”」）\n?\!]+|.+$")
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

    @novel.command("read", alias={"读"})
    async def novel_read(self, event: AstrMessageEvent, chapter_number: int = 0):
        """阅读小说，可指定章节号"""
        session_id = self._get_session_id(event)
        if chapter_number > 0:
            novel = await self.storage.get_active_novel(session_id, load_content=False)
            if novel is None:
                yield event.plain_result(
                    "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
                )
                return
            for ch in novel.chapters:
                if ch.number == chapter_number:
                    content = await self.storage.load_chapter_content(novel.id, ch.id) or ""
                    display = chapter_display(ch)
                    async for result in self._yield_segmented(
                        event, content, header=f"{display} {ch.title}"
                    ):
                        yield result
                    return
            yield event.plain_result(f"未找到第{chapter_number}章。")
        else:
            novel = await self.storage.get_active_novel(session_id, load_content=False)
            if novel is None:
                yield event.plain_result(
                    "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
                )
                return
            lines = [f"📖 「{novel.name}」概览"]
            total_words = sum(ch.content_length for ch in novel.chapters)
            lines.append(f"角色：{len(novel.characters)} 个")
            lines.append(f"关系：{len(novel.relationships)} 条")
            lines.append(f"事件：{len(novel.events)} 个")
            lines.append(f"大纲：{len(novel.outlines)} 条")
            lines.append(f"世界观设定：{len(novel.world_settings)} 条")
            lines.append(f"章节：{len(novel.chapters)} 章（共 {total_words} 字）")
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
                for ch in sorted(novel.chapters, key=lambda x: x.order):
                    lines.append(f"  {chapter_display(ch)} {ch.title}")
            async for result in self._yield_segmented(event, "\n".join(lines)):
                yield result

    @novel.command("chapters", alias={"章节"})
    async def novel_chapters(self, event: AstrMessageEvent):
        """列出所有章节"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id, load_content=False)
        if novel is None:
            yield event.plain_result(
                "当前没有激活的小说，请先使用 /novel create 创建或 /novel switch 切换一本小说。"
            )
            return
        if not novel.chapters:
            yield event.plain_result("当前小说暂无章节，使用 /novel write 开始创作吧！")
            return
        lines = [f"📚 「{novel.name}」章节列表："]
        total_words = 0
        for ch in sorted(novel.chapters, key=lambda x: x.order):
            content_len = ch.content_length
            total_words += content_len
            lines.append(f"  {chapter_display(ch)} {ch.title}（{content_len}字）")
        lines.append(f"  ── 共 {total_words} 字")
        yield event.plain_result("\n".join(lines))

    @novel.command("stop", alias={"停止"})
    async def novel_stop(self, event: AstrMessageEvent):
        """结束当前创作会话"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id, load_content=False)
        if novel is None:
            yield event.plain_result("当前没有激活的小说。")
            return
        await self.storage.remove_active_novel(session_id)
        yield event.plain_result(
            f"小说「{novel.name}」的创作会话已结束，数据已保存。使用 /novel switch 可重新激活。"
        )

    @novel.command("download", alias={"下载"})
    async def novel_download(self, event: AstrMessageEvent, *, chapter_number: int = 0):
        """下载小说TXT文件，可指定章节号，不指定则下载全本"""
        session_id = self._get_session_id(event)
        novel = await self.storage.get_active_novel(session_id, load_content=False)
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
            content = await self.storage.load_chapter_content(novel.id, target_ch.id) or ""
            if not content:
                yield event.plain_result(f"{chapter_display(target_ch)}「{target_ch.title}」暂无内容。")
                return
            display = chapter_display(target_ch)
            filename = f"{novel.name}_{display}_{target_ch.title}.txt"
            body = f"{novel.name}\n{display} {target_ch.title}\n\n{content}"
        else:
            sorted_chapters = sorted(novel.chapters, key=lambda x: x.order)
            filename = f"{novel.name}_全本.txt"

        safe_filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        tmp_dir = Path(tempfile.gettempdir()) / "astrbot_novel"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        # Clean up old temp files (> 1 hour)
        for f in tmp_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < time.time() - 3600:
                try:
                    f.unlink()
                except OSError:
                    pass
        tmp_path = tmp_dir / safe_filename
        if chapter_number > 0:
            tmp_path.write_text(body, encoding="utf-8")
        else:
            # Stream full novel to file chapter by chapter to avoid holding all content in memory
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(f"{novel.name}\n{'=' * len(novel.name)}\n")
                for ch in sorted_chapters:
                    display = chapter_display(ch)
                    f.write(f"\n{display} {ch.title}\n")
                    ch_content = await self.storage.load_chapter_content(novel.id, ch.id) or ""
                    f.write(ch_content if ch_content else "（本章暂无内容）")
                    f.write("\n")
        # Send file: use AstrBot file service if configured, otherwise base64 encode
        # to support cross-container deployments (e.g. AstrBot + NapCat in separate containers)
        try:
            from astrbot.core import astrbot_config as _cfg

            _has_file_service = bool(_cfg.get("callback_api_base"))
        except ImportError:
            _has_file_service = False

        if _has_file_service:
            chain = [Comp.File(name=safe_filename, file=str(tmp_path))]
        else:
            file_bytes = tmp_path.read_bytes()
            b64 = base64.b64encode(file_bytes).decode("ascii")
            file_comp = Comp.File(name=safe_filename)
            file_comp.url = f"base64://{b64}"
            chain = [file_comp]
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
        load_content = cfg.get("needs_content", True)
        strip_content = cfg.get("strip_content", False)
        # Type coercions for known numeric/boolean fields
        _int_fields = {"number", "order"}
        _float_fields: set[str] = set()
        _bool_fields = {"is_extra"}
        _list_fields = {"involved_characters"}

        async def handler(novel_id):
            novel = await self.storage.load_novel(novel_id, load_content=load_content)
            if novel is None:
                return jsonify({"error": "Novel not found"}), 404
            items = getattr(novel, collection_name)
            if request.method == "GET":
                serialized = [dataclasses.asdict(item) for item in items]
                if strip_content:
                    for d in serialized:
                        d.pop("content", None)
                return jsonify(serialized)
            elif request.method == "POST":
                data = await request.get_json() or {}
                kwargs = {}
                for f in create_fields:
                    val = data.get(f, "" if f not in _list_fields else [])
                    if f in _int_fields and isinstance(val, str) and val != "":
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            val = 0
                    elif f in _float_fields and isinstance(val, str) and val != "":
                        try:
                            val = float(val)
                        except (ValueError, TypeError):
                            val = 0.0
                    elif f in _bool_fields and not isinstance(val, bool):
                        val = str(val).lower() in ("true", "1", "yes")
                    elif f in _list_fields and not isinstance(val, list):
                        val = []
                    kwargs[f] = val
                if "number" in kwargs and kwargs["number"] == "":
                    kwargs["number"] = max((item.number for item in items), default=0) + 1
                if "order" in kwargs and kwargs["order"] == "":
                    kwargs["order"] = max((item.order for item in items), default=0.0) + 1.0
                item = model_cls(**kwargs)
                items.append(item)
                if sort_after_create:
                    items.sort(key=lambda x: x.order)
                await self.storage.save_novel(novel)
                return jsonify(dataclasses.asdict(item))

        return handler

    def _make_crud_item_handler(self, collection_name: str, cfg: dict):
        model_cls = cfg["model"]
        sort_after_update = cfg.get("sort_after_create", False)
        load_content = cfg.get("needs_content", True)

        async def handler(novel_id, item_id):
            novel = await self.storage.load_novel(novel_id, load_content=load_content)
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
                editable = {k: v for k, v in data.items() if k in model_cls.EDITABLE_FIELDS}
                for item in items:
                    if item.id == item_id:
                        item.apply_updates(editable)
                        if sort_after_update:
                            items.sort(key=lambda x: x.order)
                        await self.storage.save_novel(novel)
                        return jsonify(dataclasses.asdict(item))
                return jsonify({"error": f"{collection_name.rstrip('s').capitalize()} not found"}), 404

        return handler
