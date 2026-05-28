* [x] 插件基础结构完整：`metadata.yaml`、`_conf_schema.json`、`requirements.txt`、`main.py` 均存在且格式正确

* [x] 插件可被 AstrBot 正确加载，无导入错误

* [x] 数据模型定义完整：Novel、Character、Relationship、Event、Outline、Chapter 所有 dataclass 定义正确

* [x] 存储层实现正确：`NovelStorage` 类封装了 JSON 文件读写和 KV 存储操作，存储路径遵循 `data/plugin_data/` 规范

* [x] `/novel` 指令组注册成功，无子指令时展示树形帮助

* [x] `/novel create` 子指令可创建新小说并自动激活

* [x] `/novel switch` 子指令可切换当前群聊的激活小说

* [x] `/novel list` 子指令可列出所有小说并标注激活状态

* [x] `/novel delete` 子指令可删除小说及其数据

* [x] 群聊激活互斥逻辑正确：一个群聊同时只能激活一本小说

* [x] 无激活小说时执行需要激活小说的指令会提示用户

* [x] 角色画像管理 Tool（CharacterTool）可被 Agent 正确调用，CRUD 操作正常

* [x] 角色关系管理 Tool（RelationshipTool）可被 Agent 正确调用，CRUD 操作正常

* [x] 事件管理 Tool（EventTool）可被 Agent 正确调用，CRUD 操作正常

* [x] 剧情大纲管理 Tool（OutlineTool）可被 Agent 正确调用，CRUD 操作正常

* [x] 章节内容管理 Tool（ChapterTool）可被 Agent 正确调用，CRUD 操作正常

* [x] `/novel write` 子指令可调用 `tool_loop_agent` 携带 Tool 集完成创作

* [x] `/novel revise` 子指令可调用 `tool_loop_agent` 携带 Tool 集修正内容

* [x] `/novel ask` 子指令可调用 `tool_loop_agent` 基于小说内容回答问题

* [x] `/novel read` 子指令可阅读指定章节或小说概览

* [x] `/novel chapters` 子指令可列出所有章节

* [x] `/novel stop` 子指令可结束创作会话并保存状态

* [x] Plugin Page 后端 API 注册正确，路由前缀为插件名

* [x] Plugin Page 前端可通过 Bridge API 正确调用后端 API

* [x] Plugin Page 可展示小说列表、小说详情（角色、关系、事件、大纲、章节）

* [x] Plugin Page 可编辑小说数据并持久化

* [x] 数据持久化正确：重启后数据可恢复

* [x] 代码通过 ruff 格式化检查

* [x] 无 `requests` 库使用，异步操作使用 `async/await`

