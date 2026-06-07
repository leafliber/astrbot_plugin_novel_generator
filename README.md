<p align="center">
  <img src="https://moe-counter.glitch.me/get/@astrbot_plugin_novel_generator" alt="Visitors">
</p>

<h1 align="center">✨ 小说创作Agent ✨</h1>

<p align="center"><strong>让 AI 成为你的专属小说家 — 从角色设定到章节正文，一条指令全自动创作</strong></p>

## 它能做什么？

告诉它你想写什么，它会自己搞定剩下的一切——建立角色档案、编织人物关系、规划剧情大纲、逐章撰写正文。

```
/novel write 写一个赛博朋克题材的悬疑故事，主角是个地下黑客，偶然发现公司暗藏的意识上传实验
```

Agent 会自动调用内部工具完成：创建角色 → 建立关系 → 设定世界观 → 规划大纲 → 撰写章节正文。你只需要下达创作意图，结构化的数据管理交给它。

### 创作中的 Agent 工具调用

Agent 在创作过程中可自主调用 6 个内部工具：

| 工具 | 说明 |
|---|---|
| 角色画像 | 管理角色的姓名、性格、外貌、背景、备注 |
| 角色关系 | 管理角色间的关系类型和描述 |
| 事件管理 | 管理事件名、时间线、描述、涉及角色 |
| 剧情大纲 | 管理大纲标题、章节规划、情节走向，支持层级结构 |
| 章节管理 | 创建章节、分段追加正文、更新摘要和元数据 |
| 世界观设定 | 管理时代、地理、魔法体系、社会结构等设定 |

## 功能亮点

- **Agent 驱动** — 基于 AstrBot `tool_loop_agent`，LLM 自主规划创作流程并调用工具
- **结构化数据** — 角色、关系、事件、大纲、章节、世界观全部结构化存储，支持查询和修改
- **长篇连贯** — 自动维护故事梗概和章节摘要，跨章节保持情节连贯
- **可配置隔离** — 支持分群隔离（默认）、分用户隔离、不隔离三种模式
- **所有权转让** — 支持在群聊中转让小说所有权给其他用户或群组
- **Web 管理面板** — 内嵌于 AstrBot Dashboard，可视化浏览和编辑所有数据
- **安全存储** — 原子写入 + 并发锁，不怕崩溃和竞争
- **导出下载** — 支持下载单章或全本 TXT 文件

## 快速开始

### 安装

在 AstrBot 插件市场搜索「小说创作Agent」安装，或手动克隆：

```bash
git clone https://github.com/leafliber/astrbot_plugin_novel_generator.git \
  AstrBot/data/plugins/astrbot_plugin_novel_generator/
```

### 五分钟创作一本小说

```
/novel 创建 星海漂流              # 1. 创建小说
/novel 写 写一个太空冒险故事       # 2. 开始创作，Agent 自动完成所有工作
/novel 章节                       # 3. 查看章节列表
/novel 读 1                       # 4. 阅读第一章
/novel 写 继续写第二章             # 5. 继续创作
/novel 问 主角和船长是什么关系     # 6. 随时提问
/novel 下载                       # 7. 下载全本
```

## 指令一览

所有指令通过 `/novel`（或 `/小说`）指令组使用，支持中文别名：

### 创作管理

| 指令 | 别名 | 说明 | 示例 |
|---|---|---|---|
| `create <名称>` | `创建` | 创建新小说并激活 | `/novel 创建 星海漂流` |
| `switch <名称>` | `切换` | 切换到已有小说 | `/novel 切换 星海漂流` |
| `list` | `列表` | 列出当前可见的小说 | `/novel 列表` |
| `delete <名称>` | `删除` | 删除小说 | `/novel 删除 废弃草稿` |
| `transfer <名称>` | `转让` | 转让小说所有权 | `/novel 转让 @用户 小说名` |
| `stop` | `停止` | 结束当前创作会话（数据保留） | `/novel 停止` |

### 创作与交互

| 指令 | 别名 | 说明 | 示例 |
|---|---|---|---|
| `write <要求>` | `写` | 创作或修改小说，Agent 自主调用工具 | `/novel 写 主角发现了一个秘密` |
| `ask <问题>` | `问` | 对小说提问，Agent 查询数据回答 | `/novel 问 主角的背景是什么` |

### 阅读与导出

| 指令 | 别名 | 说明 | 示例 |
|---|---|---|---|
| `read` | `读` | 阅读小说概览 | `/novel 读` |
| `read <章节号>` | `读` | 阅读指定章节 | `/novel 读 3` |
| `chapters` | `章节` | 查看章节列表及状态 | `/novel 章节` |
| `download` | `下载` | 下载全本 TXT | `/novel 下载` |
| `download <章节号>` | `下载` | 下载单章 TXT | `/novel 下载 1` |

### 关于转让指令

`/novel transfer`（`/novel 转让`）的行为取决于当前隔离模式：

| 隔离模式 | 用法 | 效果 |
|---|---|---|
| `group` | `/novel 转让 小说名` | 归属改为当前群聊（私聊则改为当前用户） |
| `user` | `/novel 转让 @目标用户 小说名` | 归属改为 @ 的目标用户 |
| `none` | `/novel 转让 小说名` | 更新归属字段（当前不影响可见性） |

## 配置项

在 AstrBot WebUI 插件配置页可调整：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `provider_id` | 空 | 模型提供商，留空使用当前会话默认 |
| `max_agent_steps` | `30` | Agent 最大执行步骤数 |
| `tool_call_timeout` | `60` | 单次工具调用超时（秒） |
| `novel_system_prompt` | 内置提示词 | 自定义创作系统提示词，留空使用内置 |
| `segment_max_length` | `2000` | 消息分段最大字符数，≤ 0 不分段 |
| `segment_delay` | `5` | 分段发送间隔（秒），含 0-1 秒随机抖动 |
| `session_isolation` | `group` | 会话隔离模式：`group`(分群)、`user`(分用户)、`none`(不隔离) |

## 项目结构

```
astrbot_plugin_novel_generator/
├── main.py              # 插件入口：指令注册 + Web API
├── models.py            # 数据模型：Novel, Character, Chapter 等
├── storage.py           # 存储层：原子写入 + 并发锁 + 索引
├── tools.py             # Agent 工具定义（6 个 FunctionTool）
├── pages/
│   └── novel-manager/   # Web 管理面板前端
├── tests/               # 单元测试（160 项）
├── _conf_schema.json    # 配置项定义
├── metadata.yaml        # 插件元数据
└── requirements.txt     # 依赖
```

## 许可证

[GPL-3.0](LICENSE)
