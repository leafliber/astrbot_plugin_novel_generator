from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from astrbot.api import logger

from .models import Novel


PLUGIN_NAME = "astrbot_plugin_novel_generator"


class NovelStorage:
    def __init__(self, data_base_path: Path):
        self._novels_dir = data_base_path / "plugin_data" / PLUGIN_NAME / "novels"
        self._novels_dir.mkdir(parents=True, exist_ok=True)
        self._kv_plugin = None

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

    async def get_active_novel(self, session_id: str) -> Optional[Novel]:
        novel_id = await self._get_active_novel_id(session_id)
        if novel_id is None:
            return None
        return await self.load_novel(novel_id)

    async def set_active_novel(self, session_id: str, novel_id: str):
        await self._set_active_novel_id(session_id, novel_id)

    async def remove_active_novel(self, session_id: str):
        await self._remove_active_novel_id(session_id)

    def _novel_path(self, novel_id: str) -> Path:
        return self._novels_dir / f"{novel_id}.json"

    def _save_novel_sync(self, novel: Novel):
        novel.updated_at = datetime.now().isoformat()
        path = self._novel_path(novel.id)
        path.write_text(
            json.dumps(novel.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load_novel_sync(self, novel_id: str) -> Optional[Novel]:
        path = self._novel_path(novel_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Novel.from_dict(data)

    def _delete_novel_sync(self, novel_id: str) -> bool:
        path = self._novel_path(novel_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def _list_novels_sync(self) -> list[Novel]:
        novels = []
        for path in self._novels_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                novels.append(Novel.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load novel from {path}: {e}")
        return novels

    async def save_novel(self, novel: Novel):
        await asyncio.to_thread(self._save_novel_sync, novel)

    async def load_novel(self, novel_id: str) -> Optional[Novel]:
        return await asyncio.to_thread(self._load_novel_sync, novel_id)

    async def delete_novel(self, novel_id: str) -> bool:
        return await asyncio.to_thread(self._delete_novel_sync, novel_id)

    async def list_novels(self) -> list[Novel]:
        return await asyncio.to_thread(self._list_novels_sync)

    async def list_novel_summaries(self) -> list[dict]:
        novels = await self.list_novels()
        return [
            {
                "id": n.id,
                "name": n.name,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
                "chapter_count": len(n.chapters),
                "character_count": len(n.characters),
            }
            for n in novels
        ]
