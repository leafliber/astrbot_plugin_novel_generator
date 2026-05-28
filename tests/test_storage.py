from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot_plugin_novel_generator.models import (
    Character,
    Chapter,
    Novel,
)
from astrbot_plugin_novel_generator.storage import NovelStorage, PLUGIN_NAME


@pytest.fixture
def tmp_data_base(tmp_path):
    return tmp_path


@pytest.fixture
def storage(tmp_data_base):
    return NovelStorage(tmp_data_base)


@pytest.fixture
def kv_plugin():
    plugin = MagicMock()
    plugin.get_kv_data = AsyncMock(return_value=None)
    plugin.put_kv_data = AsyncMock()
    plugin.delete_kv_data = AsyncMock()
    return plugin


@pytest.fixture
def storage_with_kv(tmp_data_base, kv_plugin):
    s = NovelStorage(tmp_data_base)
    s.set_kv_plugin(kv_plugin)
    return s


@pytest.fixture
def sample_novel():
    return Novel(
        name="测试小说",
        characters=[Character(name="张三", personality="勇敢")],
        chapters=[Chapter(number=1, title="开端", content="内容")],
    )


class TestNovelStorageInit:
    def test_creates_directory(self, tmp_data_base):
        NovelStorage(tmp_data_base)
        expected = tmp_data_base / "plugin_data" / PLUGIN_NAME / "novels"
        assert expected.exists()
        assert expected.is_dir()

    def test_novels_dir_path(self, storage, tmp_data_base):
        expected = tmp_data_base / "plugin_data" / PLUGIN_NAME / "novels"
        assert storage._novels_dir == expected


class TestNovelStorageCRUD:
    def test_save_and_load_novel(self, storage, sample_novel):
        storage.save_novel(sample_novel)
        loaded = storage.load_novel(sample_novel.id)
        assert loaded is not None
        assert loaded.name == "测试小说"
        assert len(loaded.characters) == 1
        assert loaded.characters[0].name == "张三"
        assert len(loaded.chapters) == 1

    def test_save_updates_timestamp(self, storage, sample_novel):
        storage.save_novel(sample_novel)
        first_updated = sample_novel.updated_at
        import time

        time.sleep(0.01)
        storage.save_novel(sample_novel)
        loaded = storage.load_novel(sample_novel.id)
        assert loaded.updated_at >= first_updated

    def test_load_nonexistent_novel(self, storage):
        result = storage.load_novel("nonexistent_id")
        assert result is None

    def test_delete_novel(self, storage, sample_novel):
        storage.save_novel(sample_novel)
        assert storage.load_novel(sample_novel.id) is not None
        result = storage.delete_novel(sample_novel.id)
        assert result is True
        assert storage.load_novel(sample_novel.id) is None

    def test_delete_nonexistent_novel(self, storage):
        result = storage.delete_novel("nonexistent_id")
        assert result is False

    def test_save_creates_json_file(self, storage, sample_novel):
        storage.save_novel(sample_novel)
        path = storage._novel_path(sample_novel.id)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "测试小说"

    def test_json_file_encoding_utf8(self, storage):
        novel = Novel(name="中文小说名 🎭")
        storage.save_novel(novel)
        path = storage._novel_path(novel.id)
        content = path.read_text(encoding="utf-8")
        assert "中文小说名 🎭" in content


class TestNovelStorageList:
    def test_list_novels_empty(self, storage):
        novels = storage.list_novels()
        assert novels == []

    def test_list_novels_multiple(self, storage):
        n1 = Novel(name="小说1")
        n2 = Novel(name="小说2")
        storage.save_novel(n1)
        storage.save_novel(n2)
        novels = storage.list_novels()
        assert len(novels) == 2
        names = {n.name for n in novels}
        assert names == {"小说1", "小说2"}

    def test_list_novel_summaries(self, storage, sample_novel):
        storage.save_novel(sample_novel)
        summaries = storage.list_novel_summaries()
        assert len(summaries) == 1
        s = summaries[0]
        assert s["name"] == "测试小说"
        assert s["chapter_count"] == 1
        assert s["character_count"] == 1
        assert "id" in s
        assert "created_at" in s
        assert "updated_at" in s

    def test_list_novels_skips_corrupt_file(self, storage):
        corrupt_path = storage._novels_dir / "corrupt.json"
        corrupt_path.write_text("not valid json{{{", encoding="utf-8")
        n = Novel(name="正常小说")
        storage.save_novel(n)
        novels = storage.list_novels()
        assert len(novels) == 1
        assert novels[0].name == "正常小说"


class TestNovelStorageKV:
    @pytest.mark.asyncio
    async def test_get_active_novel_no_kv(self, storage):
        result = await storage.get_active_novel("session1")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_active_novel(self, storage_with_kv, sample_novel):
        storage_with_kv.save_novel(sample_novel)
        storage_with_kv._kv_plugin.get_kv_data = AsyncMock(
            return_value=sample_novel.id
        )
        await storage_with_kv.set_active_novel("session1", sample_novel.id)
        novel = await storage_with_kv.get_active_novel("session1")
        assert novel is not None
        assert novel.id == sample_novel.id

    @pytest.mark.asyncio
    async def test_remove_active_novel(self, storage_with_kv):
        await storage_with_kv.remove_active_novel("session1")
        storage_with_kv._kv_plugin.delete_kv_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_novel_nonexistent_id(self, storage_with_kv):
        storage_with_kv._kv_plugin.get_kv_data = AsyncMock(return_value="nonexistent")
        result = await storage_with_kv.get_active_novel("session1")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_active_novel_kv_key_format(self, storage_with_kv):
        await storage_with_kv.set_active_novel("group_123", "novel_abc")
        storage_with_kv._kv_plugin.put_kv_data.assert_called_once_with(
            "active_novel:group_123", "novel_abc"
        )


class TestNovelStoragePath:
    def test_novel_path(self, storage, tmp_data_base):
        path = storage._novel_path("abc123")
        expected = (
            tmp_data_base
            / "plugin_data"
            / PLUGIN_NAME
            / "novels"
            / "abc123.json"
        )
        assert path == expected
