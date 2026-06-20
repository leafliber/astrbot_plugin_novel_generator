from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrbot_plugin_novel_generator.models import (
    Character,
    Chapter,
    Novel,
)
from astrbot_plugin_novel_generator.storage import NovelStorage


@pytest.fixture
def tmp_data_base(tmp_path):
    return tmp_path


def _make_event(session_id="test_session", user_id="test_user", group_id=""):
    event = MagicMock()
    event.unified_msg_origin = session_id
    event.message_obj = MagicMock()
    event.message_obj.group_id = group_id
    event.message_obj.sender = MagicMock()
    event.message_obj.sender.user_id = user_id
    event.plain_result = MagicMock(return_value=MagicMock())
    return event


def _make_context(storage):
    context = MagicMock()
    context.get_current_chat_provider_id = AsyncMock(return_value="test_provider")
    context.tool_loop_agent = AsyncMock()
    context.register_web_api = MagicMock()
    return context


def _make_config():
    return MagicMock(
        get=MagicMock(
            side_effect=lambda key, default=None: {
                "novel_system_prompt": "你是一个小说创作助手",
                "max_agent_steps": 30,
                "tool_call_timeout": 60,
                "segment_max_length": 2000,
                "segment_delay": 5,
                "session_isolation": "group",
            }.get(key, default)
        )
    )


def _make_storage(tmp_data_base):
    s = NovelStorage(tmp_data_base)
    s._get_active_novel_id = AsyncMock(return_value=None)
    s._set_active_novel_id = AsyncMock()
    s._remove_active_novel_id = AsyncMock()
    s.get_active_novel = AsyncMock(return_value=None)
    s.set_active_novel = AsyncMock()
    s.remove_active_novel = AsyncMock()
    return s


@patch("astrbot_plugin_novel_generator.main.NovelStorage")
class TestNovelGeneratorPluginInit:
    def test_init_creates_storage(self, MockStorage, tmp_data_base):
        mock_storage = _make_storage(tmp_data_base)
        MockStorage.return_value = mock_storage
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        context = _make_context(None)
        config = _make_config()
        plugin = NovelGeneratorPlugin(context, config)
        assert plugin.storage is not None
        assert plugin.config is not None

    def test_init_registers_web_apis(self, MockStorage, tmp_data_base):
        mock_storage = _make_storage(tmp_data_base)
        MockStorage.return_value = mock_storage
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        context = _make_context(None)
        config = _make_config()
        NovelGeneratorPlugin(context, config)
        assert context.register_web_api.call_count == 18

    @pytest.mark.asyncio
    async def test_terminate(self, MockStorage, tmp_data_base):
        mock_storage = _make_storage(tmp_data_base)
        MockStorage.return_value = mock_storage
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        context = _make_context(None)
        config = _make_config()
        plugin = NovelGeneratorPlugin(context, config)
        await plugin.terminate()


class TestNovelCreate:
    @pytest.mark.asyncio
    async def test_create_novel(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        event = _make_event()
        gen = plugin.novel_create(event, name="新小说")
        await gen.__anext__()
        event.plain_result.assert_called_once()
        call_args = event.plain_result.call_args[0][0]
        assert "新小说" in call_args
        assert "已创建" in call_args

    @pytest.mark.asyncio
    async def test_create_novel_saves_and_activates(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        event = _make_event()
        gen = plugin.novel_create(event, name="测试")
        await gen.__anext__()
        novels = await storage.list_novels()
        assert len(novels) == 1
        assert novels[0].name == "测试"
        storage.set_active_novel.assert_called_once()


class TestNovelSwitch:
    @pytest.mark.asyncio
    async def test_switch_existing_novel(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(name="目标小说")
        await storage.save_novel(novel)
        event = _make_event()
        gen = plugin.novel_switch(event, name="目标小说")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "已切换" in call_args

    @pytest.mark.asyncio
    async def test_switch_nonexistent_novel(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        event = _make_event()
        gen = plugin.novel_switch(event, name="不存在的小说")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "未找到" in call_args


class TestNovelList:
    @pytest.mark.asyncio
    async def test_list_empty(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        event = _make_event()
        gen = plugin.novel_list(event)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "暂无" in call_args

    @pytest.mark.asyncio
    async def test_list_with_novels(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        await storage.save_novel(Novel(name="小说A"))
        await storage.save_novel(Novel(name="小说B"))
        event = _make_event()
        gen = plugin.novel_list(event)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "小说A" in call_args
        assert "小说B" in call_args

    @pytest.mark.asyncio
    async def test_list_marks_active(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(name="当前小说")
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        event = _make_event()
        gen = plugin.novel_list(event)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "当前" in call_args


class TestNovelDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(name="待删除")
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=None)
        event = _make_event()
        gen = plugin.novel_delete(event, name="待删除")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "已删除" in call_args
        assert await storage.load_novel(novel.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        event = _make_event()
        gen = plugin.novel_delete(event, name="不存在")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "未找到" in call_args

    @pytest.mark.asyncio
    async def test_delete_active_novel_removes_activation(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(name="活跃小说")
        await storage.save_novel(novel)
        storage._get_active_novel_id = AsyncMock(return_value=novel.id)
        event = _make_event()
        gen = plugin.novel_delete(event, name="活跃小说")
        await gen.__anext__()
        storage.remove_active_novel.assert_called_once()


class TestNovelWrite:
    @pytest.mark.asyncio
    async def test_write_no_active_novel(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        plugin.context = _make_context(storage)
        storage.get_active_novel = AsyncMock(return_value=None)
        event = _make_event()
        gen = plugin.novel_write(event, requirement="写一段冒险故事")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "没有激活" in call_args

    @pytest.mark.asyncio
    async def test_write_calls_agent(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        context = _make_context(storage)
        plugin.context = context
        novel = Novel(name="创作中")
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        mock_resp = MagicMock()
        mock_resp.completion_text = "生成的故事内容"
        context.tool_loop_agent = AsyncMock(return_value=mock_resp)
        with patch("astrbot_plugin_novel_generator.main.ToolSet"):
            event = _make_event()
            gen = plugin.novel_write(event, requirement="写一段冒险故事")
            await gen.__anext__()  # "正在创作中" prompt
            await gen.__anext__()
            context.tool_loop_agent.assert_called_once()
            call_kwargs = context.tool_loop_agent.call_args
            assert "冒险故事" in call_kwargs.kwargs["prompt"]


class TestNovelAsk:
    @pytest.mark.asyncio
    async def test_ask_no_active_novel(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        plugin.context = _make_context(storage)
        storage.get_active_novel = AsyncMock(return_value=None)
        event = _make_event()
        gen = plugin.novel_ask(event, question="主角是谁")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "没有激活" in call_args

    @pytest.mark.asyncio
    async def test_ask_calls_agent(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        context = _make_context(storage)
        plugin.context = context
        novel = Novel(name="提问中")
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        mock_resp = MagicMock()
        mock_resp.completion_text = "主角是张三"
        context.tool_loop_agent = AsyncMock(return_value=mock_resp)
        with patch("astrbot_plugin_novel_generator.main.ToolSet") as mock_toolset:
            event = _make_event()
            gen = plugin.novel_ask(event, question="主角是谁")
            await gen.__anext__()  # "正在思考中" prompt
            await gen.__anext__()
            context.tool_loop_agent.assert_called_once()
            call_kwargs = context.tool_loop_agent.call_args.kwargs
            # ask uses readonly system prompt (not the write one)
            assert "阅读助手" in call_kwargs["system_prompt"]
            # ToolSet receives readonly tools (class names end with "Readonly")
            toolset_arg = mock_toolset.call_args[0][0]
            tool_cls_names = [type(t).__name__ for t in toolset_arg]
            assert all("Readonly" in n for n in tool_cls_names)


class TestNovelRead:
    @pytest.mark.asyncio
    async def test_read_no_active_novel(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        storage.get_active_novel = AsyncMock(return_value=None)
        event = _make_event()
        gen = plugin.novel_read(event)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "没有激活" in call_args

    @pytest.mark.asyncio
    async def test_read_overview(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(
            name="阅读小说",
            characters=[Character(name="张三")],
            chapters=[Chapter(number=1, title="第一章")],
        )
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        event = _make_event()
        gen = plugin.novel_read(event)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "阅读小说" in call_args
        assert "张三" in call_args

    @pytest.mark.asyncio
    async def test_read_specific_chapter(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(
            name="章节小说",
            chapters=[Chapter(number=1, title="开端", content="正文内容")],
        )
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        event = _make_event()
        gen = plugin.novel_read(event, chapter_ref="1")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "开端" in call_args
        assert "正文内容" in call_args

    @pytest.mark.asyncio
    async def test_read_special_chapter_by_label(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(
            name="特殊章节小说",
            chapters=[
                Chapter(number=1, order=1.0, title="第一章", content="正文一"),
                Chapter(number=0, order=0.0, title="缘起", label="序章", content="序章正文"),
                Chapter(number=0, order=2.0, title="回忆", is_extra=True, content="番外正文"),
            ],
        )
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        storage.load_chapter_content = AsyncMock(return_value="序章正文")
        event = _make_event()
        gen = plugin.novel_read(event, chapter_ref="序章")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "序章" in call_args
        assert "缘起" in call_args
        assert "序章正文" in call_args

    @pytest.mark.asyncio
    async def test_read_special_chapter_extra(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(
            name="番外小说",
            chapters=[
                Chapter(number=0, order=1.0, title="回忆", is_extra=True, content="番外正文"),
            ],
        )
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        storage.load_chapter_content = AsyncMock(return_value="番外正文")
        event = _make_event()
        # is_extra without label → display "番外·回忆"; "番外" should fuzzy-match it
        gen = plugin.novel_read(event, chapter_ref="番外")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "回忆" in call_args
        assert "番外正文" in call_args

    @pytest.mark.asyncio
    async def test_read_nonexistent_chapter(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(name="无章节", chapters=[Chapter(number=1, title="第一章")])
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        event = _make_event()
        gen = plugin.novel_read(event, chapter_ref="99")
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "未找到" in call_args
        assert "第一章" in call_args


class TestNovelChapters:
    @pytest.mark.asyncio
    async def test_chapters_no_active_novel(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        storage.get_active_novel = AsyncMock(return_value=None)
        event = _make_event()
        gen = plugin.novel_chapters(event)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "没有激活" in call_args


@patch("astrbot_plugin_novel_generator.main.NovelStorage")
class TestWebAPIRegistration:
    @patch("astrbot_plugin_novel_generator.main.NovelStorage")
    def test_api_registration_count(self, MockStorage, tmp_data_base):
        mock_storage = _make_storage(tmp_data_base)
        MockStorage.return_value = mock_storage
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        context = _make_context(None)
        config = _make_config()
        NovelGeneratorPlugin(context, config)
        assert context.register_web_api.call_count == 18

    @patch("astrbot_plugin_novel_generator.main.NovelStorage")
    def test_api_registration_paths(self, MockStorage, tmp_data_base):
        mock_storage = _make_storage(tmp_data_base)
        MockStorage.return_value = mock_storage
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        context = _make_context(None)
        config = _make_config()
        NovelGeneratorPlugin(context, config)
        registered_paths = [
            call.args[0] for call in context.register_web_api.call_args_list
        ]
        assert any("/novels" in p and "novel_id" not in p for p in registered_paths)
        assert any("characters" in p for p in registered_paths)
        assert any("relationships" in p for p in registered_paths)
        assert any("events" in p for p in registered_paths)
        assert any("outlines" in p for p in registered_paths)
        assert any("chapters" in p for p in registered_paths)


class TestSplitText:
    def test_short_text_returns_single_segment(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        result = NovelGeneratorPlugin._split_text("短文本", max_length=2000)
        assert result == ["短文本"]

    def test_text_fits_with_header(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        result = NovelGeneratorPlugin._split_text("短文本", max_length=2000, header="标题")
        assert result == ["标题\n\n短文本"]

    def test_splits_on_paragraph_boundaries(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        # 3 paragraphs, each ~25 chars, max_length=30
        para = "这是第一段内容，用来测试段落分割功能是否正常工作。"
        text = f"{para}\n\n{para}\n\n{para}"
        result = NovelGeneratorPlugin._split_text(text, max_length=30)
        assert len(result) > 1
        for seg in result:
            assert len(seg) <= 30

    def test_splits_oversized_paragraph_by_sentences(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        # Single paragraph with multiple sentences, no \n\n breaks
        text = "这是第一句话。这是第二句话。这是第三句话。这是第四句话。这是第五句话。"
        result = NovelGeneratorPlugin._split_text(text, max_length=30)
        assert len(result) > 1
        for seg in result:
            assert len(seg) <= 30

    def test_hard_splits_no_punctuation(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        text = "a" * 100
        result = NovelGeneratorPlugin._split_text(text, max_length=30)
        assert len(result) == 4  # 30+30+30+10
        for seg in result:
            assert len(seg) <= 30

    def test_header_only_in_first_segment(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        para = "段落内容" * 50
        text = f"{para}\n\n{para}"
        result = NovelGeneratorPlugin._split_text(text, max_length=200, header="第一章 标题")
        assert result[0].startswith("第一章 标题\n\n")
        for seg in result[1:]:
            assert not seg.startswith("第一章")

    def test_header_too_long_returns_single(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        result = NovelGeneratorPlugin._split_text("内容", max_length=5, header="很长的标题")
        assert len(result) == 1


class TestYieldSegmented:
    def _make_plugin(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.config = _make_config()
        return plugin

    @pytest.mark.asyncio
    async def test_disabled_yields_single_message(self):
        plugin = self._make_plugin()
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda key, default=None: {"segment_max_length": 0, "segment_delay": 0}.get(key, default))
        )
        event = _make_event()
        results = []
        async for r in plugin._yield_segmented(event, "长文本内容"):
            results.append(r)
        assert len(results) == 1
        event.plain_result.assert_called_once_with("长文本内容")

    @pytest.mark.asyncio
    async def test_short_text_no_index_prefix(self):
        plugin = self._make_plugin()
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda key, default=None: {"segment_max_length": 2000, "segment_delay": 0}.get(key, default))
        )
        event = _make_event()
        results = []
        async for r in plugin._yield_segmented(event, "短文本"):
            results.append(r)
        assert len(results) == 1
        call_arg = event.plain_result.call_args[0][0]
        assert not call_arg.startswith("[1/")

    @pytest.mark.asyncio
    async def test_long_text_has_index_prefix(self):
        plugin = self._make_plugin()
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda key, default=None: {"segment_max_length": 10, "segment_delay": 0}.get(key, default))
        )
        event = _make_event()
        results = []
        text = "第一段内容。第二段内容。第三段内容。第四段内容。"
        async for r in plugin._yield_segmented(event, text):
            results.append(r)
        assert len(results) > 1
        for i, call in enumerate(event.plain_result.call_args_list):
            arg = call[0][0]
            assert arg.startswith(f"[{i + 1}/")

    @pytest.mark.asyncio
    async def test_delay_between_segments(self):
        plugin = self._make_plugin()
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda key, default=None: {"segment_max_length": 10, "segment_delay": 2}.get(key, default))
        )
        event = _make_event()
        with patch("astrbot_plugin_novel_generator.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            text = "第一句。第二句。第三句。第四句。"
            results = []
            async for r in plugin._yield_segmented(event, text):
                results.append(r)
            if len(results) > 1:
                assert mock_sleep.call_count == len(results) - 1
                for call in mock_sleep.call_args_list:
                    delay_val = call[0][0]
                    assert delay_val >= 2 and delay_val <= 3  # 2 + random(0,1)

    @pytest.mark.asyncio
    async def test_header_passed_through(self):
        plugin = self._make_plugin()
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda key, default=None: {"segment_max_length": 2000, "segment_delay": 0}.get(key, default))
        )
        event = _make_event()
        results = []
        async for r in plugin._yield_segmented(event, "正文", header="第一章 标题"):
            results.append(r)
        assert len(results) == 1
        call_arg = event.plain_result.call_args[0][0]
        assert call_arg == "第一章 标题\n\n正文"


class TestBuildContextInfo:
    @pytest.fixture(autouse=True)
    def _import_plugin(self):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin
        self.Plugin = NovelGeneratorPlugin

    def test_synopsis_shown(self):
        novel = Novel(name="测试", synopsis="这是一个关于冒险的故事。")
        info = self.Plugin._build_context_info(novel)
        assert "故事梗概" in info
        assert "冒险" in info

    def test_synopsis_absent(self):
        novel = Novel(name="测试")
        info = self.Plugin._build_context_info(novel)
        assert "故事梗概" not in info

    def test_chapter_summary_preferred_over_content(self):
        ch = Chapter(number=1, order=1.0, title="开端", content="很久很久以前...", summary="主角出发了")
        novel = Novel(name="测试", chapters=[ch])
        info = self.Plugin._build_context_info(novel)
        assert "主角出发了" in info
        assert "很久很久以前" not in info

    def test_chapter_content_fallback(self):
        ch = Chapter(number=1, order=1.0, title="开端", content="很久很久以前...")
        novel = Novel(name="测试", chapters=[ch])
        info = self.Plugin._build_context_info(novel)
        assert "很久很久以前" in info

    def test_character_background_shown(self):
        c = Character(name="张三", personality="勇敢", background="来自北方小村")
        novel = Novel(name="测试", characters=[c])
        info = self.Plugin._build_context_info(novel)
        assert "北方小村" in info


class TestComputeSessionId:
    def test_group_mode_returns_unified_msg_origin(self):
        from astrbot_plugin_novel_generator.main import compute_session_id
        event = _make_event(session_id="aiocqhttp:GroupMessage:Group:123:qq")
        assert compute_session_id(event, "group") == "aiocqhttp:GroupMessage:Group:123:qq"

    def test_user_mode_returns_user_prefix(self):
        from astrbot_plugin_novel_generator.main import compute_session_id
        event = _make_event(user_id="user_abc")
        assert compute_session_id(event, "user") == "user:user_abc"

    def test_none_mode_returns_global(self):
        from astrbot_plugin_novel_generator.main import compute_session_id
        event = _make_event()
        assert compute_session_id(event, "none") == "_global"

    def test_unknown_mode_defaults_to_group(self):
        from astrbot_plugin_novel_generator.main import compute_session_id
        event = _make_event(session_id="group:123")
        assert compute_session_id(event, "unknown") == "group:123"


class TestGetSessionId:
    @pytest.mark.asyncio
    async def test_session_id_default_group(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        event = _make_event(session_id="group_123")
        assert plugin._get_session_id(event) == "group_123"

    @pytest.mark.asyncio
    async def test_session_id_user_mode(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "user"}.get(k, d))
        )
        plugin.config = config
        event = _make_event(session_id="group_123", user_id="user_xyz")
        assert plugin._get_session_id(event) == "user:user_xyz"

    @pytest.mark.asyncio
    async def test_session_id_none_mode(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "none"}.get(k, d))
        )
        plugin.config = config
        event = _make_event(session_id="group_123")
        assert plugin._get_session_id(event) == "_global"


class TestGetNovelFilter:
    @pytest.fixture
    def plugin(self, tmp_data_base):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin
        storage = _make_storage(tmp_data_base)
        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            p = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        p.storage = storage
        p.config = _make_config()
        return p

    def test_group_mode_with_group_id(self, plugin):
        event = _make_event(group_id="group_123")
        f = plugin._get_novel_filter(event)
        assert f == {"owner_group_id": "group_123"}

    def test_group_mode_private_chat(self, plugin):
        event = _make_event(user_id="user_abc", group_id="")
        f = plugin._get_novel_filter(event)
        assert f == {"owner_user_id": "user_abc"}

    def test_user_mode(self, plugin):
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "user"}.get(k, d))
        )
        event = _make_event(user_id="user_abc")
        f = plugin._get_novel_filter(event)
        assert f == {"owner_user_id": "user_abc"}

    def test_none_mode(self, plugin):
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "none"}.get(k, d))
        )
        event = _make_event()
        f = plugin._get_novel_filter(event)
        assert f == {}


class TestNovelTransfer:
    @pytest.fixture
    def plugin(self, tmp_data_base):
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin
        storage = NovelStorage(tmp_data_base)
        mock_kv = MagicMock()
        mock_kv.get_kv_data = AsyncMock(return_value=None)
        mock_kv.put_kv_data = AsyncMock()
        mock_kv.delete_kv_data = AsyncMock()
        storage.set_kv_plugin(mock_kv)
        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            p = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        p.storage = storage
        p.config = _make_config()
        return p

    @pytest.mark.asyncio
    async def test_user_mode_with_at(self, plugin, tmp_data_base):
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "user"}.get(k, d))
        )
        novel = Novel(name="测试转移", owner_user_id="user_a")
        await plugin.storage.save_novel(novel)

        at_mock = MagicMock(spec=[])
        at_mock.qq = "user_b"
        event = _make_event(user_id="user_a")
        event.message_obj.message = [MagicMock(spec=[]), at_mock]
        results = []
        async for r in plugin.novel_transfer(event, "测试转移"):
            results.append(r)
        transferred = await plugin.storage.load_novel(novel.id, load_content=False)
        assert transferred.owner_user_id == "user_b"

    @pytest.mark.asyncio
    async def test_user_mode_without_at_error(self, plugin, tmp_data_base):
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "user"}.get(k, d))
        )
        novel = Novel(name="测试转移", owner_user_id="user_a")
        await plugin.storage.save_novel(novel)

        event = _make_event(user_id="user_a")
        event.message_obj.message = [MagicMock(spec=[])]  # no 'qq' attribute
        results = []
        async for r in plugin.novel_transfer(event, "测试转移"):
            results.append(r)
        assert "需要 @mention" in event.plain_result.call_args[0][0]

    @pytest.mark.asyncio
    async def test_group_mode_in_group(self, plugin, tmp_data_base):
        novel = Novel(name="测试转移", owner_user_id="user_a", owner_group_id="group_old")
        await plugin.storage.save_novel(novel)

        event = _make_event(user_id="user_a", group_id="group_new")
        event.message_obj.message = []
        results = []
        async for r in plugin.novel_transfer(event, "测试转移"):
            results.append(r)
        transferred = await plugin.storage.load_novel(novel.id, load_content=False)
        assert transferred.owner_group_id == "group_new"

    @pytest.mark.asyncio
    async def test_none_mode(self, plugin, tmp_data_base):
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "none"}.get(k, d))
        )
        novel = Novel(name="测试转移", owner_user_id="user_a")
        await plugin.storage.save_novel(novel)

        event = _make_event(user_id="user_a", group_id="group_new")
        event.message_obj.message = []
        results = []
        async for r in plugin.novel_transfer(event, "测试转移"):
            results.append(r)
        transferred = await plugin.storage.load_novel(novel.id, load_content=False)
        assert transferred.owner_group_id == "group_new"

    @pytest.mark.asyncio
    async def test_not_found(self, plugin, tmp_data_base):
        event = _make_event(user_id="user_a")
        event.message_obj.message = []
        results = []
        async for r in plugin.novel_transfer(event, "不存在的小说"):
            results.append(r)
        assert "未找到" in event.plain_result.call_args[0][0]

    @pytest.mark.asyncio
    async def test_clears_active_after_transfer(self, plugin, tmp_data_base):
        plugin.config = MagicMock(
            get=MagicMock(side_effect=lambda k, d=None: {"session_isolation": "user"}.get(k, d))
        )
        novel = Novel(name="测试转移", owner_user_id="user_a")
        await plugin.storage.save_novel(novel)

        at_mock = MagicMock()
        at_mock.qq = "user_b"
        event = _make_event(user_id="user_a")
        event.message_obj.message = [at_mock]

        plugin.storage._kv_plugin.get_kv_data = AsyncMock(return_value=novel.id)
        plugin.storage._kv_plugin.delete_kv_data = AsyncMock()

        results = []
        async for r in plugin.novel_transfer(event, "测试转移"):
            results.append(r)
        plugin.storage._kv_plugin.delete_kv_data.assert_called_once()
