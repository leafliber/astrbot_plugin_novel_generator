# 📖 AstrBot 小说创作器

**基于 AstrBot Agent 的小说创作与管理插件 | 结构化数据管理 | Web 管理面板**

## ✨ 功能特色

- 🤖 **Agent 驱动创作** - 通过 AstrBot 的 `tool_loop_agent` 调用 LLM，自动使用工具管理角色、关系、事件、大纲和章节
- 🧩 **5 大内部工具** - 角色画像、角色关系、事件管理、剧情大纲、章节管理，Agent 可自主调用完成结构化创作
- 📚 **完整指令组** - 统一的 `/novel` 指令组，涵盖创建、切换、写作、修正、阅读、提问、章节列表、停止等全流程
- 🔒 **群聊互斥激活** - 每个群聊同时只能激活一本小说，避免创作混乱
- 💾 **轻量存储** - JSON 文件存储小说数据，KV 存储管理激活状态，无需额外数据库
- 🌐 **Web 管理面板** - 基于 AstrBot Plugin Pages 的可视化面板，内嵌于 Dashboard，支持所有数据的增删改查

## 📦 安装

### 方式一：插件市场

在 AstrBot WebUI 的插件市场中搜索「小说创作器」并安装

### 方式二：手动安装

将本仓库克隆或下载到 AstrBot 的插件目录：

```bash
git clone https://github.com/cassia/astrbot_plugin_novel_generator.git AstrBot/data/plugins/astrbot_plugin_novel_generator/
```

然后在 AstrBot WebUI 的「插件管理」页面点击「重载插件」

## 🎛️ 配置项

在 AstrBot WebUI 的插件配置页面可调整以下选项：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `max_agent_steps` | `30` | Agent 最大执行步骤数，控制单次创作中的最大执行步骤 |
| `tool_call_timeout` | `60` | 工具调用超时时间（秒） |
| `novel_system_prompt` | 内置提示词 | Agent 创作时使用的系统提示词，可根据需要自定义 |

## 📱 指令使用

所有指令通过 `/novel` 指令组统一管理：

### 创作管理

| 指令 | 说明 | 示例 |
|---|---|---|
| `/novel create <名称>` | 创建一本新小说并激活 | `/novel create 星际迷途` |
| `/novel switch <名称>` | 切换到指定小说 | `/novel switch 星际迷途` |
| `/novel list` | 列出所有小说 | `/novel list` |
| `/novel delete <名称>` | 删除指定小说 | `/novel delete 废弃草稿` |
| `/novel stop` | 结束当前创作会话（数据保留） | `/novel stop` |

### 创作与交互

| 指令 | 说明 | 示例 |
|---|---|---|
| `/novel write <要求>` | 写故事，传入创作要求，Agent 将自动使用工具管理数据 | `/novel write 写一段主角发现秘密的情节` |
| `/novel revise <要求>` | 修正故事，传入修改要求 | `/novel revise 把第三章的结局改得更悬疑` |
| `/novel ask <问题>` | 对当前小说提问，Agent 可查询数据回答 | `/novel ask 主角和反派是什么关系` |

### 阅读与浏览

| 指令 | 说明 | 示例 |
|---|---|---|
| `/novel read` | 阅读小说概览（角色、章节目录等） | `/novel read` |
| `/novel read <章节号>` | 阅读指定章节内容 | `/novel read 3` |
| `/novel chapters` | 列出所有章节及字数 | `/novel chapters` |

## 🧩 Agent 内部工具

插件为 Agent 提供 5 个内部工具，Agent 在创作过程中可自主调用：

| 工具 | 名称 | 支持的操作 | 说明 |
|---|---|---|---|
| 角色画像 | `manage_character` | create / query / update / delete / list | 管理角色的姓名、性格、外貌、背景、备注 |
| 角色关系 | `manage_relationship` | create / query / update / delete / list | 管理角色间的关系类型和描述 |
| 事件管理 | `manage_event` | create / query / update / delete / list | 管理事件名、时间线位置、描述、涉及角色 |
| 剧情大纲 | `manage_outline` | create / query / update / delete / list | 管理大纲标题、章节规划、情节走向、备注 |
| 章节管理 | `manage_chapter` | create / query / update / list | 管理章节号、标题、正文内容 |

> 这些工具仅在 `/novel write`、`/novel revise`、`/novel ask` 指令触发 Agent 时可用，不会暴露给 AstrBot 全局。

## 🌐 Web 管理面板

在 AstrBot Dashboard 的插件页面中可直接访问管理界面，支持：

- 小说列表查看与概览统计
- 角色画像的增删改查
- 角色关系的管理
- 事件的创建与编辑
- 剧情大纲的维护
- 章节内容的查看与编辑

## 📊 数据存储

### 小说数据

每本小说以独立 JSON 文件存储：

```
data/plugin_data/astrbot_plugin_novel_generator/novels/
├── a1b2c3d4e5f6.json
├── f7e8d9c0b1a2.json
└── ...
```

### 激活状态

群聊的激活小说映射通过 AstrBot KV 存储管理：

```
active_novel:<session_id> → <novel_id>
```

### 数据结构

每本小说的 JSON 文件包含以下结构：

```json
{
  "id": "a1b2c3d4e5f6",
  "name": "星际迷途",
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-02T12:00:00",
  "characters": [
    {
      "id": "abc12345",
      "name": "林远",
      "personality": "冷静果断",
      "appearance": "身材高大，目光锐利",
      "background": "退役军官",
      "notes": "主角"
    }
  ],
  "relationships": [
    {
      "id": "rel12345",
      "character_a": "林远",
      "character_b": "苏晴",
      "relation_type": "搭档",
      "description": "生死与共的战友"
    }
  ],
  "events": [
    {
      "id": "evt12345",
      "name": "信号事件",
      "timeline_position": "第一章",
      "description": "收到来自深空的神秘信号",
      "involved_characters": ["林远", "苏晴"]
    }
  ],
  "outlines": [
    {
      "id": "out12345",
      "title": "主线大纲",
      "chapter_plan": "1-5章：发现信号；6-10章：深入调查",
      "plot_direction": "从悬疑走向冒险",
      "notes": "注意伏笔回收"
    }
  ],
  "chapters": [
    {
      "id": "ch1234567",
      "number": 1,
      "title": "信号",
      "content": "夜幕降临，基地的通讯阵列突然..."
    }
  ]
}
```

## 🔗 Web API 列表

插件注册了以下 Web API 端点（前缀 `/astrbot_plugin_novel_generator/`）：

| 端点 | 方法 | 说明 |
|---|---|---|
| `novels` | GET | 获取小说列表（含概览统计） |
| `novels/{novel_id}` | GET | 获取小说详情 |
| `novels/{novel_id}/characters` | GET / POST | 角色列表 / 新增角色 |
| `novels/{novel_id}/characters/{item_id}` | POST | 角色更新 / 删除（`_action` 字段区分） |
| `novels/{novel_id}/relationships` | GET / POST | 关系列表 / 新增关系 |
| `novels/{novel_id}/relationships/{item_id}` | POST | 关系更新 / 删除 |
| `novels/{novel_id}/events` | GET / POST | 事件列表 / 新增事件 |
| `novels/{novel_id}/events/{item_id}` | POST | 事件更新 / 删除 |
| `novels/{novel_id}/outlines` | GET / POST | 大纲列表 / 新增大纲 |
| `novels/{novel_id}/outlines/{item_id}` | POST | 大纲更新 / 删除 |
| `novels/{novel_id}/chapters` | GET / POST | 章节列表 / 新增章节 |
| `novels/{novel_id}/chapters/{item_id}` | POST | 章节更新 / 删除 |

> 由于 AstrBot Bridge API 仅支持 `apiGet` 和 `apiPost`，更新和删除操作均通过 POST 方法，请求体中的 `_action` 字段（`update` 或 `delete`）区分操作类型。

## 🏗️ 项目结构

```
astrbot_plugin_novel_generator/
├── main.py              # 插件主入口，指令注册与 Web API
├── models.py            # 数据模型定义（Novel, Character 等）
├── storage.py           # 存储层（JSON 文件读写 + KV 存储）
├── tools.py             # Agent 内部工具定义（5 个 FunctionTool）
├── pages/
│   └── novel-manager/   # Web 管理面板前端
│       ├── index.html
│       ├── style.css
│       └── app.js
├── tests/               # 单元测试
├── _conf_schema.json    # 配置项定义
├── metadata.yaml        # 插件元数据
└── requirements.txt     # 依赖列表
```

## 🛠️ 开发

### 本地调试

1. 克隆本插件仓库
2. 将插件目录放入 `AstrBot/data/plugins/`
3. 启动 AstrBot，在 WebUI 重载插件

### 运行测试

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install pytest pytest-asyncio pydantic quart astrbot

# 运行测试
python -m pytest tests/ -v
```

### 代码检查

```bash
pip install ruff
ruff check .
```

## 📄 许可证

[GPL-3.0](LICENSE)
