from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional

from astrbot.api import logger

from .models import Novel


PLUGIN_NAME = "astrbot_plugin_novel_generator"

MAX_LOCKS = 128


class NovelStorage:
    def __init__(self, data_base_path: Path):
        self._novels_dir = data_base_path / "plugin_data" / PLUGIN_NAME / "novels"
        self._novels_dir.mkdir(parents=True, exist_ok=True)
        self._kv_plugin = None
        self._novel_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()

    def _get_lock(self, novel_id: str) -> asyncio.Lock:
        if novel_id in self._novel_locks:
            self._novel_locks.move_to_end(novel_id)
        else:
            if len(self._novel_locks) >= MAX_LOCKS:
                self._novel_locks.popitem(last=False)
            self._novel_locks[novel_id] = asyncio.Lock()
        return self._novel_locks[novel_id]

    def set_kv_plugin(self, plugin_instance):
        self._kv_plugin = plugin_instance

    async def _get_active_novel_id(self, session_id: str) -> Optional[str]:
        if self._kv_plugin is None:
            return None
        key = f"active_novel:{session_id}"
        return await self._kv_plugin.get_kv_data(key, None)

    async def _set_active_novel_id(self, session_id: str, novel_id: str):
        if self._kv_plugin is None:
            return
        key = f"active_novel:{session_id}"
        await self._kv_plugin.put_kv_data(key, novel_id)

    async def _remove_active_novel_id(self, session_id: str):
        if self._kv_plugin is None:
            return
        key = f"active_novel:{session_id}"
        await self._kv_plugin.delete_kv_data(key)

    async def get_active_novel(self, session_id: str, *, load_content: bool = True) -> Optional[Novel]:
        novel_id = await self._get_active_novel_id(session_id)
        if novel_id is None:
            return None
        return await self.load_novel(novel_id, load_content=load_content)

    async def set_active_novel(self, session_id: str, novel_id: str):
        await self._set_active_novel_id(session_id, novel_id)

    async def remove_active_novel(self, session_id: str):
        await self._remove_active_novel_id(session_id)

    def _novel_path(self, novel_id: str) -> Path:
        return self._novels_dir / f"{novel_id}.json"

    def _index_path(self) -> Path:
        return self._novels_dir / "_index.json"

    def _read_index_sync(self) -> list[dict]:
        path = self._index_path()
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_index_sync(self, entries: list[dict]):
        path = self._index_path()
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, path)

    def _rebuild_index_sync(self) -> list[dict]:
        entries = []
        for path in self._novels_dir.glob("*.json"):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entries.append(
                    {
                        "id": data.get("id", ""),
                        "name": data.get("name", ""),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "chapter_count": len(data.get("chapters", [])),
                        "character_count": len(data.get("characters", [])),
                    }
                )
            except Exception as e:
                logger.error(f"Failed to index novel from {path}: {e}")
        self._write_index_sync(entries)
        return entries

    def _update_index_entry_sync(self, novel: Novel):
        entries = self._read_index_sync()
        new_entry = {
            "id": novel.id,
            "name": novel.name,
            "created_at": novel.created_at,
            "updated_at": novel.updated_at,
            "chapter_count": len(novel.chapters),
            "character_count": len(novel.characters),
        }
        found = False
        for i, entry in enumerate(entries):
            if entry.get("id") == novel.id:
                entries[i] = new_entry
                found = True
                break
        if not found:
            entries.append(new_entry)
        self._write_index_sync(entries)

    def _remove_index_entry_sync(self, novel_id: str):
        entries = self._read_index_sync()
        entries = [e for e in entries if e.get("id") != novel_id]
        self._write_index_sync(entries)

    def _chapters_dir(self, novel_id: str) -> Path:
        d = self._novels_dir / novel_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _chapter_path(self, novel_id: str, chapter_id: str) -> Path:
        return self._chapters_dir(novel_id) / f"{chapter_id}.txt"

    def _save_novel_sync(self, novel: Novel, save_content: bool = True):
        novel.updated_at = datetime.now().isoformat()
        if save_content:
            chapters_dir = self._chapters_dir(novel.id)
            for ch in novel.chapters:
                ch_path = self._chapter_path(novel.id, ch.id)
                tmp_ch = ch_path.with_suffix(".tmp")
                tmp_ch.write_text(ch.content, encoding="utf-8")
                os.replace(tmp_ch, ch_path)
        novel_dict = novel.to_dict()
        for ch_dict in novel_dict.get("chapters", []):
            ch_dict.pop("content", None)
        path = self._novel_path(novel.id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(novel_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, path)
        self._update_index_entry_sync(novel)

    def _load_novel_sync(self, novel_id: str, load_content: bool = True) -> Optional[Novel]:
        path = self._novel_path(novel_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if load_content:
            for ch_dict in data.get("chapters", []):
                ch_id = ch_dict.get("id", "")
                ch_path = self._chapter_path(novel_id, ch_id)
                if ch_path.exists():
                    ch_dict["content"] = ch_path.read_text(encoding="utf-8")
                else:
                    ch_dict["content"] = ch_dict.get("content", "")
        return Novel.from_dict(data)

    def _delete_novel_sync(self, novel_id: str) -> bool:
        path = self._novel_path(novel_id)
        chapters_dir = self._novels_dir / novel_id
        deleted = False
        if path.exists():
            path.unlink()
            deleted = True
        if chapters_dir.exists():
            shutil.rmtree(chapters_dir)
            deleted = True
        if deleted:
            self._remove_index_entry_sync(novel_id)
        return deleted

    def _list_novels_sync(self) -> list[Novel]:
        novels = []
        for path in self._novels_dir.glob("*.json"):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                novels.append(Novel.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load novel from {path}: {e}")
        return novels

    async def save_novel(self, novel: Novel, *, save_content: bool = True):
        async with self._get_lock(novel.id):
            await asyncio.to_thread(self._save_novel_sync, novel, save_content)

    async def load_novel(self, novel_id: str, *, load_content: bool = True) -> Optional[Novel]:
        async with self._get_lock(novel_id):
            return await asyncio.to_thread(self._load_novel_sync, novel_id, load_content)

    async def delete_novel(self, novel_id: str) -> bool:
        async with self._get_lock(novel_id):
            result = await asyncio.to_thread(self._delete_novel_sync, novel_id)
        if result and novel_id in self._novel_locks:
            del self._novel_locks[novel_id]
        return result

    async def list_novels(self) -> list[Novel]:
        return await asyncio.to_thread(self._list_novels_sync)

    async def list_novel_summaries(self) -> list[dict]:
        entries = await asyncio.to_thread(self._read_index_sync)
        if not entries:
            entries = await asyncio.to_thread(self._rebuild_index_sync)
        return entries

    async def find_novel_summary_by_name(self, name: str) -> Optional[dict]:
        entries = await asyncio.to_thread(self._read_index_sync)
        if not entries:
            entries = await asyncio.to_thread(self._rebuild_index_sync)
        for entry in entries:
            if entry.get("name") == name:
                return entry
        return None
