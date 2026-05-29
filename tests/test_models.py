from __future__ import annotations


from astrbot_plugin_novel_generator.models import (
    Character,
    Chapter,
    Event,
    Novel,
    Outline,
    Relationship,
)


class TestCharacter:
    def test_default_values(self):
        c = Character()
        assert len(c.id) == 8
        assert c.name == ""
        assert c.personality == ""
        assert c.appearance == ""
        assert c.background == ""
        assert c.notes == ""

    def test_custom_values(self):
        c = Character(
            id="abc12345",
            name="张三",
            personality="勇敢",
            appearance="高大",
            background="战士",
            notes="主角",
        )
        assert c.id == "abc12345"
        assert c.name == "张三"
        assert c.personality == "勇敢"

    def test_id_uniqueness(self):
        ids = {Character().id for _ in range(100)}
        assert len(ids) == 100


class TestRelationship:
    def test_default_values(self):
        r = Relationship()
        assert len(r.id) == 8
        assert r.character_a == ""
        assert r.character_b == ""
        assert r.relation_type == ""
        assert r.description == ""

    def test_custom_values(self):
        r = Relationship(
            character_a="张三",
            character_b="李四",
            relation_type="朋友",
            description="生死之交",
        )
        assert r.character_a == "张三"
        assert r.relation_type == "朋友"


class TestEvent:
    def test_default_values(self):
        e = Event()
        assert len(e.id) == 8
        assert e.name == ""
        assert e.timeline_position == ""
        assert e.description == ""
        assert e.involved_characters == []

    def test_custom_values(self):
        e = Event(
            name="大战",
            timeline_position="第一章",
            description="决定性战役",
            involved_characters=["张三", "李四"],
        )
        assert e.name == "大战"
        assert len(e.involved_characters) == 2

    def test_involved_characters_independent(self):
        e1 = Event()
        e2 = Event()
        e1.involved_characters.append("张三")
        assert e2.involved_characters == []


class TestOutline:
    def test_default_values(self):
        o = Outline()
        assert len(o.id) == 8
        assert o.title == ""
        assert o.chapter_plan == ""
        assert o.plot_direction == ""
        assert o.notes == ""

    def test_custom_values(self):
        o = Outline(
            title="主线",
            chapter_plan="1-5章",
            plot_direction="升级",
            notes="伏笔",
        )
        assert o.title == "主线"


class TestChapter:
    def test_default_values(self):
        ch = Chapter()
        assert len(ch.id) == 8
        assert ch.number == 0
        assert ch.title == ""
        assert ch.content == ""

    def test_custom_values(self):
        ch = Chapter(number=1, title="开端", content="很久很久以前...")
        assert ch.number == 1
        assert ch.title == "开端"


class TestNovel:
    def test_default_values(self):
        n = Novel()
        assert len(n.id) == 12
        assert n.name == ""
        assert n.created_at != ""
        assert n.updated_at != ""
        assert n.characters == []
        assert n.relationships == []
        assert n.events == []
        assert n.outlines == []
        assert n.chapters == []

    def test_custom_name(self):
        n = Novel(name="测试小说")
        assert n.name == "测试小说"

    def test_to_dict(self):
        n = Novel(
            name="测试",
            characters=[Character(name="张三")],
            chapters=[Chapter(number=1, title="第一章")],
        )
        d = n.to_dict()
        assert d["name"] == "测试"
        assert len(d["characters"]) == 1
        assert d["characters"][0]["name"] == "张三"
        assert len(d["chapters"]) == 1
        assert d["chapters"][0]["number"] == 1

    def test_from_dict_roundtrip(self):
        original = Novel(
            name="往返测试",
            characters=[Character(name="A", personality="勇敢")],
            relationships=[
                Relationship(character_a="A", character_b="B", relation_type="朋友")
            ],
            events=[Event(name="事件1", involved_characters=["A"])],
            outlines=[Outline(title="大纲1")],
            chapters=[Chapter(number=1, title="第一章", content="内容")],
        )
        d = original.to_dict()
        restored = Novel.from_dict(d)
        assert restored.name == original.name
        assert restored.id == original.id
        assert len(restored.characters) == 1
        assert restored.characters[0].name == "A"
        assert restored.characters[0].personality == "勇敢"
        assert len(restored.relationships) == 1
        assert restored.relationships[0].relation_type == "朋友"
        assert len(restored.events) == 1
        assert restored.events[0].involved_characters == ["A"]
        assert len(restored.outlines) == 1
        assert len(restored.chapters) == 1
        assert restored.chapters[0].content == "内容"

    def test_from_dict_missing_fields(self):
        d = {"name": "部分数据"}
        n = Novel.from_dict(d)
        assert n.name == "部分数据"
        assert n.characters == []
        assert n.relationships == []
        assert n.events == []
        assert n.outlines == []
        assert n.chapters == []

    def test_from_dict_empty(self):
        n = Novel.from_dict({})
        assert n.name == ""
        assert len(n.id) == 12

    def test_lists_are_independent(self):
        n1 = Novel()
        n2 = Novel()
        n1.characters.append(Character(name="张三"))
        assert n2.characters == []

    def test_to_dict_contains_all_fields(self):
        n = Novel(name="完整测试")
        d = n.to_dict()
        expected_keys = {
            "id",
            "name",
            "created_at",
            "updated_at",
            "schema_version",
            "characters",
            "relationships",
            "events",
            "outlines",
            "chapters",
            "world_settings",
        }
        assert set(d.keys()) == expected_keys
