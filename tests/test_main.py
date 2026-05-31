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


def _make_event(session_id="test_session"):
    event = MagicMock()
    event.unified_msg_origin = session_id
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
        assert context.register_web_api.call_count == 14

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
        storage.get_active_novel = AsyncMock(return_value=novel)
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
        with patch("astrbot_plugin_novel_generator.main.ToolSet"):
            event = _make_event()
            gen = plugin.novel_ask(event, question="主角是谁")
            await gen.__anext__()
            context.tool_loop_agent.assert_called_once()


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
        gen = plugin.novel_read(event, chapter_number=1)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "开端" in call_args
        assert "正文内容" in call_args

    @pytest.mark.asyncio
    async def test_read_nonexistent_chapter(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        novel = Novel(name="无章节")
        await storage.save_novel(novel)
        storage.get_active_novel = AsyncMock(return_value=novel)
        event = _make_event()
        gen = plugin.novel_read(event, chapter_number=99)
        await gen.__anext__()
        call_args = event.plain_result.call_args[0][0]
        assert "未找到" in call_args


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
        assert context.register_web_api.call_count == 14

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


class TestGetSessionId:
    @pytest.mark.asyncio
    async def test_session_id(self, tmp_data_base):
        storage = _make_storage(tmp_data_base)
        from astrbot_plugin_novel_generator.main import NovelGeneratorPlugin

        with patch.object(NovelGeneratorPlugin, "__init__", lambda self, *a, **kw: None):
            plugin = NovelGeneratorPlugin.__new__(NovelGeneratorPlugin)
        plugin.storage = storage
        plugin.config = _make_config()
        event = _make_event(session_id="group_123")
        assert plugin._get_session_id(event) == "group_123"


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
