# Tasks

- [x] Task 1: 搭建插件基础结构
  - [x] SubTask 1.1: 创建 `metadata.yaml`，填写插件元数据（name、desc、version、author 等）
  - [x] SubTask 1.2: 创建 `_conf_schema.json`，定义配置项（最大 Agent 步数、工具调用超时、存储路径等）
  - [x] SubTask 1.3: 创建 `requirements.txt`（如需额外依赖）
  - [x] SubTask 1.4: 重写 `main.py`，创建继承 `Star` 的插件主类 `NovelGeneratorPlugin`，实现 `__init__` 和 `terminate`

- [x] Task 2: 实现数据模型与存储层
  - [x] SubTask 2.1: 创建 `models.py`，定义数据模型（Novel、Character、Relationship、Event、Outline、Chapter）使用 dataclass
  - [x] SubTask 2.2: 创建 `storage.py`，实现 `NovelStorage` 类，封装 JSON 文件读写、KV 存储操作（激活状态映射）、CRUD 方法
  - [x] SubTask 2.3: 确保存储路径遵循 `data/plugin_data/astrbot_plugin_novel_generator/novels/` 规范

- [x] Task 3: 实现 /novel 指令组与基础子指令
  - [x] SubTask 3.1: 在 `main.py` 中注册 `/novel` 指令组
  - [x] SubTask 3.2: 实现 `/novel create <小说名>` 子指令
  - [x] SubTask 3.3: 实现 `/novel switch <小说名>` 子指令
  - [x] SubTask 3.4: 实现 `/novel list` 子指令
  - [x] SubTask 3.5: 实现 `/novel delete <小说名>` 子指令
  - [x] SubTask 3.6: 实现群聊激活互斥逻辑（获取/设置当前群聊激活小说）

- [x] Task 4: 实现小说内部 Tool 集
  - [x] SubTask 4.1: 创建 `tools.py`，定义角色画像管理 Tool（CharacterTool）：创建、查询、修改、删除角色
  - [x] SubTask 4.2: 定义角色关系管理 Tool（RelationshipTool）：创建、查询、修改、删除关系
  - [x] SubTask 4.3: 定义事件管理 Tool（EventTool）：创建、查询、修改、删除事件
  - [x] SubTask 4.4: 定义剧情大纲管理 Tool（OutlineTool）：创建、查询、修改、删除大纲
  - [x] SubTask 4.5: 定义章节内容管理 Tool（ChapterTool）：创建、查询、修改章节
  - [x] SubTask 4.6: 所有 Tool 继承 `FunctionTool[AstrAgentContext]`，使用 `@dataclass` 方式定义

- [x] Task 5: 实现 Agent 调用与创作指令
  - [x] SubTask 5.1: 实现 `/novel write <创作要求>` 子指令，调用 `tool_loop_agent` 携带 Tool 集
  - [x] SubTask 5.2: 实现 `/novel revise <修正要求>` 子指令，调用 `tool_loop_agent` 携带 Tool 集
  - [x] SubTask 5.3: 实现 `/novel ask <问题>` 子指令，调用 `tool_loop_agent` 携带小说上下文和 Tool 集
  - [x] SubTask 5.4: 设计合适的 system_prompt，引导 Agent 在创作时合理使用内部 Tool

- [x] Task 6: 实现阅读与查询指令
  - [x] SubTask 6.1: 实现 `/novel read [章节号]` 子指令
  - [x] SubTask 6.2: 实现 `/novel chapters` 子指令
  - [x] SubTask 6.3: 实现 `/novel stop` 子指令

- [x] Task 7: 实现 Plugin Page 后端 API
  - [x] SubTask 7.1: 在 `__init__` 中注册 Web API 路由（GET/POST novels 列表、GET/POST/PUT/DELETE 单本小说详情、GET/POST 各类子数据 CRUD）
  - [x] SubTask 7.2: 实现小说列表 API
  - [x] SubTask 7.3: 实现小说详情 API（含角色、关系、事件、大纲、章节）
  - [x] SubTask 7.4: 实现小说数据编辑 API（角色、关系、事件、大纲、章节的增删改）

- [x] Task 8: 实现 Plugin Page 前端
  - [x] SubTask 8.1: 创建 `pages/novel-manager/index.html` 基础页面结构
  - [x] SubTask 8.2: 创建 `pages/novel-manager/app.js`，使用 Bridge API 与后端交互
  - [x] SubTask 8.3: 创建 `pages/novel-manager/style.css` 样式
  - [x] SubTask 8.4: 实现小说列表展示与切换
  - [x] SubTask 8.5: 实现小说详情展示（角色、关系、事件、大纲、章节标签页）
  - [x] SubTask 8.6: 实现数据编辑功能（表单提交、实时更新）

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 2]
- [Task 4] depends on [Task 2]
- [Task 5] depends on [Task 3, Task 4]
- [Task 6] depends on [Task 3]
- [Task 7] depends on [Task 2]
- [Task 8] depends on [Task 7]
