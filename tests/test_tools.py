from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot_plugin_novel_generator.models import (
    Character,
    Chapter,
    Event,
    Novel,
    Outline,
    Relationship,
)
from astrbot_plugin_novel_generator.storage import NovelStorage
from astrbot_plugin_novel_generator.tools import (
    NOVEL_TOOLS,
    CharacterTool,
    ChapterTool,
    EventTool,
    OutlineTool,
    RelationshipTool,
    _novel_to_json,
)


@pytest.fixture
def tmp_data_base(tmp_path):
    return tmp_path


@pytest.fixture
def storage(tmp_data_base):
    s = NovelStorage(tmp_data_base)
    mock_kv = MagicMock()
    mock_kv.get_kv_data = AsyncMock(return_value=None)
    mock_kv.put_kv_data = AsyncMock()
    mock_kv.delete_kv_data = AsyncMock()
    s.set_kv_plugin(mock_kv)
    return s


@pytest.fixture
def novel(storage):
    n = Novel(name="测试小说")
    storage.save_novel(n)
    storage._kv_plugin.get_kv_data = AsyncMock(return_value=n.id)
    return n


def _make_context(storage, novel, session_id="test_session"):
    plugin_mock = MagicMock()
    plugin_mock.storage = storage

    event_mock = MagicMock()
    event_mock.unified_msg_origin = session_id

    astr_ctx = MagicMock()
    astr_ctx.context = plugin_mock
    astr_ctx.event = event_mock

    wrapper = MagicMock()
    wrapper.context = astr_ctx

    return wrapper


class TestNovelToJson:
    def test_produces_valid_json(self, novel):
        result = _novel_to_json(novel)
        parsed = json.loads(result)
        assert parsed["name"] == "测试小说"

    def test_preserves_chinese(self):
        n = Novel(name="中文小说 🎭")
        result = _novel_to_json(n)
        assert "中文小说 🎭" in result


class TestNOVELTOOLSList:
    def test_contains_all_tools(self):
        assert len(NOVEL_TOOLS) == 5
        assert CharacterTool in NOVEL_TOOLS
        assert RelationshipTool in NOVEL_TOOLS
        assert EventTool in NOVEL_TOOLS
        assert OutlineTool in NOVEL_TOOLS
        assert ChapterTool in NOVEL_TOOLS

    def test_tool_names_are_unique(self):
        names = [t().name for t in NOVEL_TOOLS]
        assert len(names) == len(set(names))


class TestCharacterTool:
    @pytest.fixture
    def tool(self):
        return CharacterTool()

    def test_name(self, tool):
        assert tool.name == "manage_character"

    def test_parameters_has_action(self, tool):
        params = tool.parameters
        if hasattr(params, "default_factory"):
            params = params.default_factory()
        assert "action" in params["properties"]
        assert "required" in params

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx,
            action="create",
            name="李四",
            personality="聪明",
            appearance="瘦高",
            background="书生",
            notes="配角",
        )
        assert "李四" in str(result)
        loaded = storage.load_novel(novel.id)
        assert len(loaded.characters) == 1
        assert loaded.characters[0].name == "李四"
        assert loaded.characters[0].personality == "聪明"

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        char = Character(name="王五", personality="豪爽")
        novel.characters.append(char)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="query", character_id=char.id)
        data = json.loads(str(result))
        assert data["name"] == "王五"
        assert data["personality"] == "豪爽"

    @pytest.mark.asyncio
    async def test_query_not_found(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="query", character_id="nonexistent")
        assert "未找到" in str(result)

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        char = Character(name="赵六", personality="内向")
        novel.characters.append(char)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx, action="update", character_id=char.id, personality="外向"
        )
        assert "已更新" in str(result)
        loaded = storage.load_novel(novel.id)
        assert loaded.characters[0].personality == "外向"
        assert loaded.characters[0].name == "赵六"

    @pytest.mark.asyncio
    async def test_update_not_found(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx, action="update", character_id="nonexistent", name="x"
        )
        assert "未找到" in str(result)

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        char = Character(name="孙七")
        novel.characters.append(char)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="delete", character_id=char.id)
        assert "已删除" in str(result)
        loaded = storage.load_novel(novel.id)
        assert len(loaded.characters) == 0

    @pytest.mark.asyncio
    async def test_delete_not_found(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="delete", character_id="nonexistent")
        assert "未找到" in str(result)

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.characters.append(Character(name="A", personality="勇敢"))
        novel.characters.append(Character(name="B", personality="聪明"))
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "A" in str(result)
        assert "B" in str(result)

    @pytest.mark.asyncio
    async def test_list_empty(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "暂无" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, tool, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        ctx = _make_context(storage, None)
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="unknown_action")
        assert "未知操作" in str(result)


class TestRelationshipTool:
    @pytest.fixture
    def tool(self):
        return RelationshipTool()

    def test_name(self, tool):
        assert tool.name == "manage_relationship"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx,
            action="create",
            character_a="张三",
            character_b="李四",
            relation_type="朋友",
            description="生死之交",
        )
        assert "已创建" in str(result)
        loaded = storage.load_novel(novel.id)
        assert len(loaded.relationships) == 1
        assert loaded.relationships[0].character_a == "张三"

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        rel = Relationship(character_a="A", character_b="B", relation_type="师徒")
        novel.relationships.append(rel)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="query", relationship_id=rel.id)
        data = json.loads(str(result))
        assert data["relation_type"] == "师徒"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        rel = Relationship(character_a="A", character_b="B", relation_type="朋友")
        novel.relationships.append(rel)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx, action="update", relationship_id=rel.id, relation_type="敌人"
        )
        assert "已更新" in str(result)
        loaded = storage.load_novel(novel.id)
        assert loaded.relationships[0].relation_type == "敌人"

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        rel = Relationship(character_a="A", character_b="B")
        novel.relationships.append(rel)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="delete", relationship_id=rel.id)
        assert "已删除" in str(result)
        loaded = storage.load_novel(novel.id)
        assert len(loaded.relationships) == 0

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.relationships.append(
            Relationship(character_a="A", character_b="B", relation_type="朋友")
        )
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "A" in str(result)
        assert "B" in str(result)

    @pytest.mark.asyncio
    async def test_list_empty(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "暂无" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, tool, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        ctx = _make_context(storage, None)
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)


class TestEventTool:
    @pytest.fixture
    def tool(self):
        return EventTool()

    def test_name(self, tool):
        assert tool.name == "manage_event"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx,
            action="create",
            name="大战",
            timeline_position="第一章",
            description="决定性战役",
            involved_characters=["张三", "李四"],
        )
        assert "大战" in str(result)
        loaded = storage.load_novel(novel.id)
        assert len(loaded.events) == 1
        assert loaded.events[0].involved_characters == ["张三", "李四"]

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        evt = Event(name="事件1", timeline_position="中期")
        novel.events.append(evt)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="query", event_id=evt.id)
        data = json.loads(str(result))
        assert data["name"] == "事件1"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        evt = Event(name="旧事件")
        novel.events.append(evt)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx, action="update", event_id=evt.id, name="新事件"
        )
        assert "已更新" in str(result)
        loaded = storage.load_novel(novel.id)
        assert loaded.events[0].name == "新事件"

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        evt = Event(name="待删事件")
        novel.events.append(evt)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="delete", event_id=evt.id)
        assert "已删除" in str(result)

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.events.append(Event(name="事件A", timeline_position="前期"))
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "事件A" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, tool, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        ctx = _make_context(storage, None)
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)


class TestOutlineTool:
    @pytest.fixture
    def tool(self):
        return OutlineTool()

    def test_name(self, tool):
        assert tool.name == "manage_outline"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx,
            action="create",
            title="主线大纲",
            chapter_plan="1-10章",
            plot_direction="升级流",
            notes="注意伏笔",
        )
        assert "主线大纲" in str(result)
        loaded = storage.load_novel(novel.id)
        assert len(loaded.outlines) == 1

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        out = Outline(title="大纲1", chapter_plan="5章")
        novel.outlines.append(out)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="query", outline_id=out.id)
        data = json.loads(str(result))
        assert data["title"] == "大纲1"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        out = Outline(title="旧大纲")
        novel.outlines.append(out)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx, action="update", outline_id=out.id, title="新大纲"
        )
        assert "已更新" in str(result)

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        out = Outline(title="待删大纲")
        novel.outlines.append(out)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="delete", outline_id=out.id)
        assert "已删除" in str(result)

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.outlines.append(Outline(title="大纲A"))
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "大纲A" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, tool, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        ctx = _make_context(storage, None)
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)


class TestChapterTool:
    @pytest.fixture
    def tool(self):
        return ChapterTool()

    def test_name(self, tool):
        assert tool.name == "manage_chapter"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx, action="create", number=1, title="开端", content="很久以前..."
        )
        assert "开端" in str(result)
        loaded = storage.load_novel(novel.id)
        assert len(loaded.chapters) == 1
        assert loaded.chapters[0].content == "很久以前..."

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        ch = Chapter(number=1, title="第一章", content="内容")
        novel.chapters.append(ch)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="query", chapter_id=ch.id)
        data = json.loads(str(result))
        assert data["title"] == "第一章"
        assert data["content"] == "内容"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        ch = Chapter(number=1, title="旧标题", content="旧内容")
        novel.chapters.append(ch)
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(
            ctx, action="update", chapter_id=ch.id, title="新标题"
        )
        assert "已更新" in str(result)
        loaded = storage.load_novel(novel.id)
        assert loaded.chapters[0].title == "新标题"
        assert loaded.chapters[0].content == "旧内容"

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.chapters.append(Chapter(number=1, title="第一章"))
        novel.chapters.append(Chapter(number=2, title="第二章"))
        storage.save_novel(novel)
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "第一章" in str(result)
        assert "第二章" in str(result)

    @pytest.mark.asyncio
    async def test_list_empty(self, tool, storage, novel):
        ctx = _make_context(storage, novel)
        result = await tool.call(ctx, action="list")
        assert "暂无" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, tool, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        ctx = _make_context(storage, None)
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)
