from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from quart import jsonify, request
from astrbot.api import AstrBotConfig
from pathlib import Path
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .storage import NovelStorage, PLUGIN_NAME
from .models import Novel
from .tools import NOVEL_TOOLS
from astrbot.core.agent.tool import ToolSet


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
        novel = Novel(name=name)
        self.storage.save_novel(novel)
        await self.storage.set_active_novel(session_id, novel.id)
        yield event.plain_result(
            f"小说「{name}」已创建并激活！使用 /novel write 开始创作。"
        )

    @novel.command("switch")
    async def novel_switch(self, event: AstrMessageEvent, name: str):
        """切换到指定小说"""
        session_id = self._get_session_id(event)
        novels = self.storage.list_novels()
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
        novels = self.storage.list_novels()
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
        novels = self.storage.list_novels()
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
        self.storage.delete_novel(target.id)
        yield event.plain_result(f"小说「{name}」已删除。")

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
        umo = event.unified_msg_origin
        prov_id = await self.context.get_current_chat_provider_id(umo=umo)
        tools = ToolSet([t() for t in NOVEL_TOOLS])
        system_prompt = self.config.get("novel_system_prompt", "")
        context_info = (
            f"当前小说：「{novel.name}」\n"
            f"已有角色：{len(novel.characters)} 个\n"
            f"已有章节：{len(novel.chapters)} 章\n"
            f"已有事件：{len(novel.events)} 个\n"
            f"已有大纲：{len(novel.outlines)} 条\n"
        )
        prompt = f"{context_info}\n用户创作要求：{requirement}"
        max_steps = self.config.get("max_agent_steps", 30)
        timeout = self.config.get("tool_call_timeout", 60)
        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=prompt,
            system_prompt=system_prompt,
            tools=tools,
            max_steps=max_steps,
            tool_call_timeout=timeout,
        )
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
        umo = event.unified_msg_origin
        prov_id = await self.context.get_current_chat_provider_id(umo=umo)
        tools = ToolSet([t() for t in NOVEL_TOOLS])
        system_prompt = self.config.get("novel_system_prompt", "")
        context_info = (
            f"当前小说：「{novel.name}」\n"
            f"已有角色：{len(novel.characters)} 个\n"
            f"已有章节：{len(novel.chapters)} 章\n"
            f"已有事件：{len(novel.events)} 个\n"
            f"已有大纲：{len(novel.outlines)} 条\n"
        )
        prompt = f"{context_info}\n用户修正要求：{requirement}\n请根据要求修改已有内容，使用工具来更新数据。"
        max_steps = self.config.get("max_agent_steps", 30)
        timeout = self.config.get("tool_call_timeout", 60)
        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=prompt,
            system_prompt=system_prompt,
            tools=tools,
            max_steps=max_steps,
            tool_call_timeout=timeout,
        )
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
        umo = event.unified_msg_origin
        prov_id = await self.context.get_current_chat_provider_id(umo=umo)
        tools = ToolSet([t() for t in NOVEL_TOOLS])
        context_info = (
            f"当前小说：「{novel.name}」\n"
            f"角色：{len(novel.characters)} 个 | 章节：{len(novel.chapters)} 章 | "
            f"事件：{len(novel.events)} 个 | 大纲：{len(novel.outlines)} 条\n"
        )
        prompt = f"{context_info}\n用户问题：{question}\n请基于小说内容回答，如需查看详细数据请使用工具查询。"
        max_steps = self.config.get("max_agent_steps", 30)
        timeout = self.config.get("tool_call_timeout", 60)
        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=prompt,
            tools=tools,
            max_steps=max_steps,
            tool_call_timeout=timeout,
        )
        yield event.plain_result(llm_resp.completion_text)

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
            lines.append(f"章节：{len(novel.chapters)} 章")
            if novel.characters:
                lines.append("\n角色列表：")
                for c in novel.characters:
                    lines.append(
                        f"  • {c.name}: {c.personality[:30] if c.personality else '无描述'}"
                    )
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
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/characters",
            self.api_crud_characters,
            ["GET", "POST"],
            "Character CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/characters/{{item_id}}",
            self.api_crud_character_item,
            ["POST"],
            "Character item CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/relationships",
            self.api_crud_relationships,
            ["GET", "POST"],
            "Relationship CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/relationships/{{item_id}}",
            self.api_crud_relationship_item,
            ["POST"],
            "Relationship item CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/events",
            self.api_crud_events,
            ["GET", "POST"],
            "Event CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/events/{{item_id}}",
            self.api_crud_event_item,
            ["POST"],
            "Event item CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/outlines",
            self.api_crud_outlines,
            ["GET", "POST"],
            "Outline CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/outlines/{{item_id}}",
            self.api_crud_outline_item,
            ["POST"],
            "Outline item CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/chapters",
            self.api_crud_chapters,
            ["GET", "POST"],
            "Chapter CRUD",
        )
        self.context.register_web_api(
            f"{prefix}/novels/{{novel_id}}/chapters/{{item_id}}",
            self.api_crud_chapter_item,
            ["POST"],
            "Chapter item CRUD",
        )

    async def api_list_novels(self):
        summaries = self.storage.list_novel_summaries()
        return jsonify(summaries)

    async def api_get_novel(self, novel_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        return jsonify(novel.to_dict())

    async def api_crud_characters(self, novel_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        if request.method == "GET":
            return jsonify([c.__dict__ for c in novel.characters])
        elif request.method == "POST":
            data = await request.get_json()
            from .models import Character as CharModel

            char = CharModel(
                name=data.get("name", ""),
                personality=data.get("personality", ""),
                appearance=data.get("appearance", ""),
                background=data.get("background", ""),
                notes=data.get("notes", ""),
            )
            novel.characters.append(char)
            self.storage.save_novel(novel)
            return jsonify(char.__dict__)

    async def api_crud_character_item(self, novel_id, item_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        data = await request.get_json()
        if data.get("_action") == "delete":
            novel.characters = [c for c in novel.characters if c.id != item_id]
            self.storage.save_novel(novel)
            return jsonify({"success": True})
        else:
            for c in novel.characters:
                if c.id == item_id:
                    for k, v in data.items():
                        if hasattr(c, k) and k != "id" and k != "_action":
                            setattr(c, k, v)
                    self.storage.save_novel(novel)
                    return jsonify(c.__dict__)
            return jsonify({"error": "Character not found"}), 404

    async def api_crud_relationships(self, novel_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        if request.method == "GET":
            return jsonify([r.__dict__ for r in novel.relationships])
        elif request.method == "POST":
            data = await request.get_json()
            from .models import Relationship as RelModel

            rel = RelModel(
                character_a=data.get("character_a", ""),
                character_b=data.get("character_b", ""),
                relation_type=data.get("relation_type", ""),
                description=data.get("description", ""),
            )
            novel.relationships.append(rel)
            self.storage.save_novel(novel)
            return jsonify(rel.__dict__)

    async def api_crud_relationship_item(self, novel_id, item_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        data = await request.get_json()
        if data.get("_action") == "delete":
            novel.relationships = [r for r in novel.relationships if r.id != item_id]
            self.storage.save_novel(novel)
            return jsonify({"success": True})
        else:
            for r in novel.relationships:
                if r.id == item_id:
                    for k, v in data.items():
                        if hasattr(r, k) and k != "id" and k != "_action":
                            setattr(r, k, v)
                    self.storage.save_novel(novel)
                    return jsonify(r.__dict__)
            return jsonify({"error": "Relationship not found"}), 404

    async def api_crud_events(self, novel_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        if request.method == "GET":
            return jsonify([e.__dict__ for e in novel.events])
        elif request.method == "POST":
            data = await request.get_json()
            from .models import Event as EventModel

            evt = EventModel(
                name=data.get("name", ""),
                timeline_position=data.get("timeline_position", ""),
                description=data.get("description", ""),
                involved_characters=data.get("involved_characters", []),
            )
            novel.events.append(evt)
            self.storage.save_novel(novel)
            return jsonify(evt.__dict__)

    async def api_crud_event_item(self, novel_id, item_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        data = await request.get_json()
        if data.get("_action") == "delete":
            novel.events = [e for e in novel.events if e.id != item_id]
            self.storage.save_novel(novel)
            return jsonify({"success": True})
        else:
            for e in novel.events:
                if e.id == item_id:
                    for k, v in data.items():
                        if hasattr(e, k) and k != "id" and k != "_action":
                            setattr(e, k, v)
                    self.storage.save_novel(novel)
                    return jsonify(e.__dict__)
            return jsonify({"error": "Event not found"}), 404

    async def api_crud_outlines(self, novel_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        if request.method == "GET":
            return jsonify([o.__dict__ for o in novel.outlines])
        elif request.method == "POST":
            data = await request.get_json()
            from .models import Outline as OutlineModel

            out = OutlineModel(
                title=data.get("title", ""),
                chapter_plan=data.get("chapter_plan", ""),
                plot_direction=data.get("plot_direction", ""),
                notes=data.get("notes", ""),
            )
            novel.outlines.append(out)
            self.storage.save_novel(novel)
            return jsonify(out.__dict__)

    async def api_crud_outline_item(self, novel_id, item_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        data = await request.get_json()
        if data.get("_action") == "delete":
            novel.outlines = [o for o in novel.outlines if o.id != item_id]
            self.storage.save_novel(novel)
            return jsonify({"success": True})
        else:
            for o in novel.outlines:
                if o.id == item_id:
                    for k, v in data.items():
                        if hasattr(o, k) and k != "id" and k != "_action":
                            setattr(o, k, v)
                    self.storage.save_novel(novel)
                    return jsonify(o.__dict__)
            return jsonify({"error": "Outline not found"}), 404

    async def api_crud_chapters(self, novel_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        if request.method == "GET":
            return jsonify([ch.__dict__ for ch in novel.chapters])
        elif request.method == "POST":
            data = await request.get_json()
            from .models import Chapter as ChapterModel

            ch = ChapterModel(
                number=data.get("number", len(novel.chapters) + 1),
                title=data.get("title", ""),
                content=data.get("content", ""),
            )
            novel.chapters.append(ch)
            novel.chapters.sort(key=lambda x: x.number)
            self.storage.save_novel(novel)
            return jsonify(ch.__dict__)

    async def api_crud_chapter_item(self, novel_id, item_id):
        novel = self.storage.load_novel(novel_id)
        if novel is None:
            return jsonify({"error": "Novel not found"}), 404
        data = await request.get_json()
        if data.get("_action") == "delete":
            novel.chapters = [ch for ch in novel.chapters if ch.id != item_id]
            self.storage.save_novel(novel)
            return jsonify({"success": True})
        else:
            for ch in novel.chapters:
                if ch.id == item_id:
                    for k, v in data.items():
                        if hasattr(ch, k) and k != "id" and k != "_action":
                            setattr(ch, k, v)
                    novel.chapters.sort(key=lambda x: x.number)
                    self.storage.save_novel(novel)
                    return jsonify(ch.__dict__)
            return jsonify({"error": "Chapter not found"}), 404
