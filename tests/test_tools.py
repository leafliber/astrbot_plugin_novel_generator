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
    NovelTool,
    OutlineTool,
    RelationshipTool,
    WorldSettingTool,
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

    async def _setup():
        await storage.save_novel(n)
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=n.id)

    import asyncio
    asyncio.get_event_loop().run_until_complete(_setup())
    return n


def _make_context(session_id="test_session"):
    event_mock = MagicMock()
    event_mock.unified_msg_origin = session_id

    astr_ctx = MagicMock()
    astr_ctx.event = event_mock

    wrapper = MagicMock()
    wrapper.context = astr_ctx

    return wrapper


class TestNovelToJson:
    def test_produces_valid_json(self, novel):
        result = json.dumps(novel.to_dict(), ensure_ascii=False)
        parsed = json.loads(result)
        assert parsed["name"] == "测试小说"

    def test_preserves_chinese(self):
        n = Novel(name="中文小说 🎭")
        result = json.dumps(n.to_dict(), ensure_ascii=False)
        assert "中文小说 🎭" in result


class TestNOVELTOOLSList:
    def test_contains_all_tools(self):
        assert len(NOVEL_TOOLS) == 7
        assert CharacterTool in NOVEL_TOOLS
        assert RelationshipTool in NOVEL_TOOLS
        assert EventTool in NOVEL_TOOLS
        assert OutlineTool in NOVEL_TOOLS
        assert ChapterTool in NOVEL_TOOLS
        assert WorldSettingTool in NOVEL_TOOLS
        assert NovelTool in NOVEL_TOOLS

    def test_tool_names_are_unique(self):
        names = [t().name for t in NOVEL_TOOLS]
        assert len(names) == len(set(names))


class TestCharacterTool:
    @pytest.fixture
    def tool(self, storage):
        return CharacterTool(storage=storage, session_id="test_session")

    def test_name(self, tool):
        assert tool.name == "manage_character"

    def test_parameters_has_action(self, tool):
        params = tool.parameters
        assert isinstance(params, dict)
        assert "action" in params["properties"]
        assert "required" in params

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context()
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
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.characters) == 1
        assert loaded.characters[0].name == "李四"
        assert loaded.characters[0].personality == "聪明"

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        char = Character(name="王五", personality="豪爽")
        novel.characters.append(char)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="query", character_id=char.id)
        data = json.loads(str(result))
        assert data["name"] == "王五"
        assert data["personality"] == "豪爽"

    @pytest.mark.asyncio
    async def test_query_not_found(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="query", character_id="nonexistent")
        assert "未找到" in str(result)

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        char = Character(name="赵六", personality="内向")
        novel.characters.append(char)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(
            ctx, action="update", character_id=char.id, personality="外向"
        )
        assert "已更新" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.characters[0].personality == "外向"
        assert loaded.characters[0].name == "赵六"

    @pytest.mark.asyncio
    async def test_update_not_found(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(
            ctx, action="update", character_id="nonexistent", name="x"
        )
        assert "未找到" in str(result)

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        char = Character(name="孙七")
        novel.characters.append(char)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="delete", character_id=char.id)
        assert "已删除" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.characters) == 0

    @pytest.mark.asyncio
    async def test_delete_not_found(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="delete", character_id="nonexistent")
        assert "未找到" in str(result)

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.characters.append(Character(name="A", personality="勇敢"))
        novel.characters.append(Character(name="B", personality="聪明"))
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "A" in str(result)
        assert "B" in str(result)

    @pytest.mark.asyncio
    async def test_list_empty(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "暂无" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        tool = CharacterTool(storage=storage, session_id="test_session")
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="unknown_action")
        assert "未知操作" in str(result)

    @pytest.mark.asyncio
    async def test_no_storage(self):
        tool = CharacterTool()
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "存储未初始化" in str(result)


class TestRelationshipTool:
    @pytest.fixture
    def tool(self, storage):
        return RelationshipTool(storage=storage, session_id="test_session")

    def test_name(self, tool):
        assert tool.name == "manage_relationship"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        # 先创建两个角色，使 resolve_character_id 能解析姓名
        char_a = Character(name="张三", personality="勇敢")
        char_b = Character(name="李四", personality="聪明")
        novel.characters.extend([char_a, char_b])
        await storage.save_novel(novel)

        ctx = _make_context()
        result = await tool.call(
            ctx,
            action="create",
            character_a="张三",
            character_b="李四",
            relation_type="朋友",
            description="生死之交",
        )
        assert "已创建" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.relationships) == 1
        # 角色姓名会被自动解析为 ID
        assert loaded.relationships[0].character_a == char_a.id
        assert loaded.relationships[0].character_b == char_b.id

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        rel = Relationship(character_a="A", character_b="B", relation_type="师徒")
        novel.relationships.append(rel)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="query", relationship_id=rel.id)
        data = json.loads(str(result))
        assert data["relation_type"] == "师徒"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        rel = Relationship(character_a="A", character_b="B", relation_type="朋友")
        novel.relationships.append(rel)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(
            ctx, action="update", relationship_id=rel.id, relation_type="敌人"
        )
        assert "已更新" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.relationships[0].relation_type == "敌人"

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        rel = Relationship(character_a="A", character_b="B")
        novel.relationships.append(rel)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="delete", relationship_id=rel.id)
        assert "已删除" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.relationships) == 0

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.relationships.append(
            Relationship(character_a="A", character_b="B", relation_type="朋友")
        )
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "A" in str(result)
        assert "B" in str(result)

    @pytest.mark.asyncio
    async def test_list_empty(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "暂无" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        tool = RelationshipTool(storage=storage, session_id="test_session")
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)


class TestEventTool:
    @pytest.fixture
    def tool(self, storage):
        return EventTool(storage=storage, session_id="test_session")

    def test_name(self, tool):
        assert tool.name == "manage_event"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        # 先创建角色，使 involved_characters 的姓名能被解析为 ID
        char_a = Character(name="张三", personality="勇敢")
        char_b = Character(name="李四", personality="聪明")
        novel.characters.extend([char_a, char_b])
        await storage.save_novel(novel)

        ctx = _make_context()
        result = await tool.call(
            ctx,
            action="create",
            name="大战",
            timeline_position="第一章",
            description="决定性战役",
            involved_characters=["张三", "李四"],
        )
        assert "大战" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.events) == 1
        # 姓名会被解析为角色 ID
        assert char_a.id in loaded.events[0].involved_characters
        assert char_b.id in loaded.events[0].involved_characters

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        evt = Event(name="事件1", timeline_position="中期")
        novel.events.append(evt)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="query", event_id=evt.id)
        data = json.loads(str(result))
        assert data["name"] == "事件1"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        evt = Event(name="旧事件")
        novel.events.append(evt)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(
            ctx, action="update", event_id=evt.id, name="新事件"
        )
        assert "已更新" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.events[0].name == "新事件"

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        evt = Event(name="待删事件")
        novel.events.append(evt)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="delete", event_id=evt.id)
        assert "已删除" in str(result)

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.events.append(Event(name="事件A", timeline_position="前期"))
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "事件A" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        tool = EventTool(storage=storage, session_id="test_session")
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)


class TestOutlineTool:
    @pytest.fixture
    def tool(self, storage):
        return OutlineTool(storage=storage, session_id="test_session")

    def test_name(self, tool):
        assert tool.name == "manage_outline"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(
            ctx,
            action="create",
            title="主线大纲",
            chapter_plan="1-10章",
            plot_direction="升级流",
            notes="注意伏笔",
        )
        assert "主线大纲" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.outlines) == 1

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        out = Outline(title="大纲1", chapter_plan="5章")
        novel.outlines.append(out)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="query", outline_id=out.id)
        data = json.loads(str(result))
        assert data["title"] == "大纲1"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        out = Outline(title="旧大纲")
        novel.outlines.append(out)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(
            ctx, action="update", outline_id=out.id, title="新大纲"
        )
        assert "已更新" in str(result)

    @pytest.mark.asyncio
    async def test_delete(self, tool, storage, novel):
        out = Outline(title="待删大纲")
        novel.outlines.append(out)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="delete", outline_id=out.id)
        assert "已删除" in str(result)

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.outlines.append(Outline(title="大纲A"))
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "大纲A" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        tool = OutlineTool(storage=storage, session_id="test_session")
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)


class TestChapterTool:
    @pytest.fixture
    def tool(self, storage):
        return ChapterTool(storage=storage, session_id="test_session")

    def test_name(self, tool):
        assert tool.name == "manage_chapter"

    @pytest.mark.asyncio
    async def test_create(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(
            ctx, action="create", number=1, title="开端", content="很久以前..."
        )
        assert "开端" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.chapters) == 1
        assert loaded.chapters[0].content == "很久以前..."

    @pytest.mark.asyncio
    async def test_query(self, tool, storage, novel):
        ch = Chapter(number=1, title="第一章", content="内容")
        novel.chapters.append(ch)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="query", chapter_id=ch.id)
        data = json.loads(str(result))
        assert data["title"] == "第一章"
        assert data["content"] == "内容"

    @pytest.mark.asyncio
    async def test_update(self, tool, storage, novel):
        ch = Chapter(number=1, title="旧标题", content="旧内容")
        novel.chapters.append(ch)
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(
            ctx, action="update", chapter_id=ch.id, title="新标题"
        )
        assert "已更新" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.chapters[0].title == "新标题"
        assert loaded.chapters[0].content == "旧内容"

    @pytest.mark.asyncio
    async def test_list(self, tool, storage, novel):
        novel.chapters.append(Chapter(number=1, title="第一章"))
        novel.chapters.append(Chapter(number=2, title="第二章"))
        await storage.save_novel(novel)
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "第一章" in str(result)
        assert "第二章" in str(result)

    @pytest.mark.asyncio
    async def test_list_empty(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "暂无" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        tool = ChapterTool(storage=storage, session_id="test_session")
        ctx = _make_context()
        result = await tool.call(ctx, action="list")
        assert "没有激活" in str(result)


class TestChapterToolReorder:
    @pytest.fixture
    def tool(self, storage):
        return ChapterTool(storage=storage, session_id="test_session")

    @pytest.fixture
    def chapters_novel(self, storage, novel):
        """Create a novel with 3 ordered chapters."""
        ch1 = Chapter(number=1, order=1.0, title="第一章")
        ch2 = Chapter(number=2, order=2.0, title="第二章")
        ch3 = Chapter(number=3, order=3.0, title="第三章")

        async def _setup():
            novel.chapters = [ch1, ch2, ch3]
            await storage.save_novel(novel)

        import asyncio
        asyncio.get_event_loop().run_until_complete(_setup())
        return novel, [ch1, ch2, ch3]

    @pytest.mark.asyncio
    async def test_reorder_full_list(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ch1, ch2, ch3 = chapters
        ctx = _make_context()
        # Reverse order: 3, 2, 1
        result = await tool.call(
            ctx, action="reorder", chapter_ids=[ch3.id, ch2.id, ch1.id]
        )
        assert "已重排" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.chapters[0].id == ch3.id
        assert loaded.chapters[0].order == 1.0
        assert loaded.chapters[1].id == ch2.id
        assert loaded.chapters[1].order == 2.0
        assert loaded.chapters[2].id == ch1.id
        assert loaded.chapters[2].order == 3.0

    @pytest.mark.asyncio
    async def test_reorder_count_mismatch(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ctx = _make_context()
        # Only pass 2 IDs for 3 chapters
        result = await tool.call(
            ctx, action="reorder", chapter_ids=[chapters[0].id, chapters[1].id]
        )
        assert "数量必须一致" in str(result)

    @pytest.mark.asyncio
    async def test_reorder_unknown_id(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ctx = _make_context()
        result = await tool.call(
            ctx,
            action="reorder",
            chapter_ids=[chapters[0].id, chapters[1].id, "nonexist"],
        )
        assert "不存在" in str(result)

    @pytest.mark.asyncio
    async def test_reorder_empty_ids(self, tool, storage, chapters_novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="reorder", chapter_ids=[])
        assert "不能为空" in str(result)


class TestChapterToolMove:
    @pytest.fixture
    def tool(self, storage):
        return ChapterTool(storage=storage, session_id="test_session")

    @pytest.fixture
    def chapters_novel(self, storage, novel):
        """Create a novel with 3 ordered chapters."""
        ch1 = Chapter(number=1, order=1.0, title="第一章")
        ch2 = Chapter(number=2, order=2.0, title="第二章")
        ch3 = Chapter(number=3, order=3.0, title="第三章")

        async def _setup():
            novel.chapters = [ch1, ch2, ch3]
            await storage.save_novel(novel)

        import asyncio
        asyncio.get_event_loop().run_until_complete(_setup())
        return novel, [ch1, ch2, ch3]

    @pytest.mark.asyncio
    async def test_move_before_middle(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ch1, ch2, ch3 = chapters
        ctx = _make_context()
        # Move ch3 before ch1 → ch3 becomes first
        result = await tool.call(
            ctx, action="move", chapter_id=ch3.id, before_chapter_id=ch1.id
        )
        assert "已移到" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.chapters[0].id == ch3.id
        assert loaded.chapters[0].order < loaded.chapters[1].order

    @pytest.mark.asyncio
    async def test_move_before_first(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ch1, ch2, ch3 = chapters
        ctx = _make_context()
        # Move ch2 before ch1 → ch2 becomes first
        result = await tool.call(
            ctx, action="move", chapter_id=ch2.id, before_chapter_id=ch1.id
        )
        assert "已移到" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.chapters[0].id == ch2.id

    @pytest.mark.asyncio
    async def test_move_after_last(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ch1, ch2, ch3 = chapters
        ctx = _make_context()
        # Move ch1 after ch3 → ch1 becomes last
        result = await tool.call(
            ctx, action="move", chapter_id=ch1.id, after_chapter_id=ch3.id
        )
        assert "已移到" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.chapters[-1].id == ch1.id

    @pytest.mark.asyncio
    async def test_move_after_middle(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ch1, ch2, ch3 = chapters
        ctx = _make_context()
        # Move ch1 after ch2 → order becomes ch2, ch1, ch3
        result = await tool.call(
            ctx, action="move", chapter_id=ch1.id, after_chapter_id=ch2.id
        )
        assert "已移到" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.chapters[0].id == ch2.id
        assert loaded.chapters[1].id == ch1.id
        assert loaded.chapters[2].id == ch3.id

    @pytest.mark.asyncio
    async def test_move_to_self_error(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ctx = _make_context()
        result = await tool.call(
            ctx, action="move", chapter_id=chapters[0].id, before_chapter_id=chapters[0].id
        )
        assert "自身" in str(result)

    @pytest.mark.asyncio
    async def test_move_no_anchor(self, tool, storage, chapters_novel):
        ctx = _make_context()
        result = await tool.call(
            ctx, action="move", chapter_id="abc"
        )
        assert "必须指定" in str(result)

    @pytest.mark.asyncio
    async def test_move_both_anchors(self, tool, storage, chapters_novel):
        novel, chapters = chapters_novel
        ctx = _make_context()
        result = await tool.call(
            ctx,
            action="move",
            chapter_id=chapters[0].id,
            before_chapter_id=chapters[1].id,
            after_chapter_id=chapters[2].id,
        )
        assert "只能指定一个" in str(result)


class TestChapterToolCreateExtras:
    @pytest.fixture
    def tool(self, storage):
        return ChapterTool(storage=storage, session_id="test_session")

    @pytest.mark.asyncio
    async def test_create_with_label_and_is_extra(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(
            ctx,
            action="create",
            number=0,
            title="前传",
            label="番外一·前传",
            is_extra=True,
        )
        assert "番外一·前传" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.chapters) == 1
        assert loaded.chapters[0].label == "番外一·前传"
        assert loaded.chapters[0].is_extra is True

    @pytest.mark.asyncio
    async def test_create_with_explicit_order(self, tool, storage, novel):
        # Create first chapter normally → order=1.0
        ctx = _make_context()
        await tool.call(ctx, action="create", number=1, title="第一章")
        # Create second with explicit order before the first → order=0.5
        result = await tool.call(
            ctx, action="create", number=0, title="序章", order=0.5, label="序章"
        )
        assert "已创建" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert len(loaded.chapters) == 2
        # Sorted by order: 序章(0.5) before 第一章(1.0)
        assert loaded.chapters[0].title == "序章"
        assert loaded.chapters[0].order == 0.5
        assert loaded.chapters[1].title == "第一章"


class TestNovelTool:
    @pytest.fixture
    def tool(self, storage):
        return NovelTool(storage=storage, session_id="test_session")

    @pytest.mark.asyncio
    async def test_update_synopsis(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(
            ctx, action="update_synopsis", synopsis="主角踏上冒险旅程，遇到了神秘导师。"
        )
        assert "已更新" in str(result)
        loaded = await storage.load_novel(novel.id)
        assert loaded.synopsis == "主角踏上冒险旅程，遇到了神秘导师。"

    @pytest.mark.asyncio
    async def test_update_synopsis_empty(self, tool, storage, novel):
        ctx = _make_context()
        result = await tool.call(ctx, action="update_synopsis", synopsis="")
        assert "不能为空" in str(result)

    @pytest.mark.asyncio
    async def test_no_active_novel(self, storage):
        storage._kv_plugin.get_kv_data = AsyncMock(return_value=None)
        tool = NovelTool(storage=storage, session_id="test_session")
        ctx = _make_context()
        result = await tool.call(ctx, action="update_synopsis", synopsis="test")
        assert "没有激活" in str(result)
