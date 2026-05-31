# AstrBot 小说创作器

**基于 AstrBot Agent 的小说创作与管理插件 | 结构化数据管理 | Web 管理面板**

## 功能特色

- **Agent 驱动创作** - 通过 AstrBot 的 `tool_loop_agent` 调用 LLM，自动使用工具管理角色、关系、事件、大纲、章节和世界观设定
- **6 大内部工具** - 角色画像、角色关系、事件管理、剧情大纲、章节管理、世界观设定，Agent 可自主调用完成结构化创作
- **完整指令组** - 统一的 `/novel` 指令组，涵盖创建、切换、写作、修正、阅读、提问、章节列表、停止等全流程
- **群聊互斥激活** - 每个群聊同时只能激活一本小说，避免创作混乱
- **安全存储** - 原子写入防止崩溃损坏，并发锁防止数据竞争，章节内容独立存储，索引文件加速列表查询
- **Web 管理面板** - 基于 AstrBot Plugin Pages 的可视化面板，内嵌于 Dashboard，支持所有数据的增删改查

## 安装

### 方式一：插件市场

在 AstrBot WebUI 的插件市场中搜索「小说创作器」并安装

### 方式二：手动安装

将本仓库克隆或下载到 AstrBot 的插件目录：

```bash
git clone https://github.com/cassia/astrbot_plugin_novel_generator.git AstrBot/data/plugins/astrbot_plugin_novel_generator/
```

然后在 AstrBot WebUI 的「插件管理」页面点击「重载插件」

## 配置项

在 AstrBot WebUI 的插件配置页面可调整以下选项：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `provider_id` | 空 | 小说创作使用的模型提供商，留空则使用当前会话默认提供商 |
| `max_agent_steps` | `30` | Agent 最大执行步骤数，控制单次创作中的最大执行步骤 |
| `tool_call_timeout` | `60` | 工具调用超时时间（秒） |
| `novel_system_prompt` | 内置提示词 | Agent 创作时使用的系统提示词，可根据需要自定义 |
| `segment_max_length` | `2000` | 分段发送时每段最大字符数，设为 0 或负数关闭分段 |
| `segment_delay` | `5` | 分段发送时每段之间的延迟（秒），实际延迟会增加 0-1 秒随机抖动 |

## 指令使用

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
| `/novel write <要求>` | 创作或修改小说，传入创作/修改要求，Agent 将自动使用工具管理数据 | `/novel write 写一段主角发现秘密的情节` |
| `/novel ask <问题>` | 对当前小说提问，Agent 可查询数据回答 | `/novel ask 主角和反派是什么关系` |

### 阅读与浏览

| 指令 | 说明 | 示例 |
|---|---|---|
| `/novel read` | 阅读小说概览（角色、世界观、章节目录等） | `/novel read` |
| `/novel read <章节号>` | 阅读指定章节内容 | `/novel read 3` |
| `/novel chapters` | 列出所有章节及状态 | `/novel chapters` |

## Agent 内部工具

插件为 Agent 提供 6 个内部工具，Agent 在创作过程中可自主调用：

| 工具 | 名称 | 支持的操作 | 说明 |
|---|---|---|---|
| 角色画像 | `manage_character` | create / query / update / delete / list | 管理角色的姓名、性格、外貌、背景、备注 |
| 角色关系 | `manage_relationship` | create / query / update / delete / list | 管理角色间的关系类型和描述，角色以 ID 引用 |
| 事件管理 | `manage_event` | create / query / update / delete / list | 管理事件名、时间线位置、描述、涉及角色（ID 引用） |
| 剧情大纲 | `manage_outline` | create / query / update / delete / list | 管理大纲标题、章节规划、情节走向、备注、层级关系、排序 |
| 章节管理 | `manage_chapter` | create / query / update / list | 管理章节号、标题、正文内容、状态、摘要 |
| 世界观设定 | `manage_world_setting` | create / query / update / delete / list | 管理世界观分类、名称、描述（时代、地理、魔法体系、社会结构等） |

> 这些工具仅在 `/novel write`、`/novel ask` 指令触发 Agent 时可用，不会暴露给 AstrBot 全局。

## Web 管理面板

在 AstrBot Dashboard 的插件页面中可直接访问管理界面，支持：

- 小说列表查看与概览统计
- 角色画像的增删改查
- 角色关系的管理
- 事件的创建与编辑
- 剧情大纲的维护（含层级和排序）
- 章节内容的查看与编辑（含状态和摘要）
- 世界观设定的管理

## 数据存储

### 存储架构

```
data/plugin_data/astrbot_plugin_novel_generator/novels/
├── _index.json                    # 小说元数据索引（加速列表查询）
├── a1b2c3d4e5f6.json              # 小说主数据（不含章节正文）
├── a1b2c3d4e5f6/                  # 章节内容目录
│   ├── ch1234567.txt              # 章节正文（独立存储）
│   └── ch7654321.txt
└── f7e8d9c0b1a2.json
```

### 安全机制

- **原子写入** - 通过临时文件 + `os.replace` 原子替换，防止写入过程中崩溃导致文件损坏
- **并发锁** - 每本小说独立的 `asyncio.Lock`，防止并发写入导致数据竞争
- **索引文件** - 维护 `_index.json` 元数据索引，列表查询无需加载完整小说数据

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
  "schema_version": 1,
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
      "character_a": "abc12345",
      "character_b": "def67890",
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
      "involved_characters": ["abc12345", "def67890"]
    }
  ],
  "outlines": [
    {
      "id": "out12345",
      "title": "主线大纲",
      "chapter_plan": "1-5章：发现信号；6-10章：深入调查",
      "plot_direction": "从悬疑走向冒险",
      "notes": "注意伏笔回收",
      "parent_id": "",
      "order": 1
    }
  ],
  "chapters": [
    {
      "id": "ch1234567",
      "number": 1,
      "title": "信号",
      "content": "",
      "status": "draft",
      "summary": "林远在基地收到神秘信号"
    }
  ],
  "world_settings": [
    {
      "id": "ws123456",
      "category": "时代",
      "name": "星际殖民时代",
      "description": "人类已进入星际殖民时代，多个星球建立了殖民地"
    }
  ]
}
```

> 章节的 `content` 字段在 JSON 中为空字符串，实际正文存储在独立的 `.txt` 文件中。

### 角色引用机制

关系和事件中的角色统一使用 **ID 引用**（而非姓名），确保角色改名后引用不会失效：

- `Relationship.character_a` / `character_b` → 存储角色 ID
- `Event.involved_characters` → 存储角色 ID 列表
- 展示时通过 `Novel.character_name_by_id()` 解析为姓名
- 创建/更新时支持传入姓名或 ID，自动解析为 ID 存储

### 章节状态

章节支持三种状态：

| 状态 | 值 | 说明 |
|---|---|---|
| 草稿 | `draft` | 默认状态，初始创作 |
| 审核中 | `review` | 内容待审核 |
| 定稿 | `final` | 内容已确认 |

### 大纲层级

大纲支持树形层级结构：

- `parent_id` 为空表示顶层大纲
- `parent_id` 指向父大纲的 ID 表示子大纲
- `order` 字段控制排序，数字越小越靠前
- list 操作以缩进树形展示层级关系

## Web API 列表

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
| `novels/{novel_id}/world_settings` | GET / POST | 世界观设定列表 / 新增设定 |
| `novels/{novel_id}/world_settings/{item_id}` | POST | 世界观设定更新 / 删除 |

> 由于 AstrBot Bridge API 仅支持 `apiGet` 和 `apiPost`，更新和删除操作均通过 POST 方法，请求体中的 `_action` 字段（`update` 或 `delete`）区分操作类型。

## 项目结构

```
astrbot_plugin_novel_generator/
├── main.py              # 插件主入口，指令注册与 Web API
├── models.py            # 数据模型定义（Novel, Character, WorldSetting 等）
├── storage.py           # 存储层（原子写入 + 并发锁 + 索引 + 章节独立存储）
├── tools.py             # Agent 内部工具定义（6 个 FunctionTool）
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

## 开发

### 本地调试

1. 克隆本插件仓库
2. 将插件目录放入 `AstrBot/data/plugins/`
3. 启动 AstrBot，在 WebUI 重载插件

### 运行测试

```bash
uv run pytest tests/test_models.py -v
```

### 代码检查

```bash
uv run ruff check .
```

## 许可证

[GPL-3.0](LICENSE)
