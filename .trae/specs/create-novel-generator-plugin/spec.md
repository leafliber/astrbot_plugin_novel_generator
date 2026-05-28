# 小说创作插件 Spec

## Why
AstrBot 目前缺少一个结构化的小说创作工具。用户希望在一个群聊中通过统一的 `/novel` 指令组，借助 LLM Agent 能力进行小说创作、管理和阅读，同时通过 Page 提供可视化管理界面。

## What Changes
- 新建 AstrBot 插件 `astrbot_plugin_novel_generator`，继承 `Star` 类
- 实现 `/novel` 指令组，包含创建、切换、写故事、修正、阅读、列出章节、提问、结束等子指令
- 在写小说流程中通过 `tool_loop_agent` 调用 Agent，注册内部 Tool（角色画像、角色关系、事件、剧情大纲等管理工具）
- 使用 AstrBot KV 存储 + JSON 文件持久化小说数据，存储路径遵循 `data/plugin_data/{plugin_name}/` 规范
- 一个群聊（session）同时只能激活一本小说，其他小说需新建或切换
- 提供 Plugin Page，可视化展示和管理所有小说内容

## Impact
- Affected specs: 新增插件，无既有功能影响
- Affected code: 项目根目录下新建完整插件结构

## ADDED Requirements

### Requirement: 插件基础结构
系统 SHALL 提供符合 AstrBot 规范的插件结构，包含 `main.py`、`metadata.yaml`、`_conf_schema.json`、`requirements.txt`。

#### Scenario: 插件被 AstrBot 正确加载
- **WHEN** AstrBot 启动并扫描插件目录
- **THEN** 插件被正确识别和加载，`metadata.yaml` 中的元数据被解析

### Requirement: /novel 指令组
系统 SHALL 提供 `/novel` 指令组，统一管理所有小说相关操作。

#### Scenario: 用户输入 /novel 无子指令
- **WHEN** 用户发送 `/novel`
- **THEN** 系统展示指令组的树形帮助结构

#### Scenario: 用户创建新小说
- **WHEN** 用户发送 `/novel create <小说名>`
- **THEN** 系统创建一本新小说并自动激活，返回创建成功提示

#### Scenario: 用户切换小说
- **WHEN** 用户发送 `/novel switch <小说名>`
- **THEN** 系统将当前群聊的激活小说切换为指定小说，返回切换成功提示

#### Scenario: 用户列出所有小说
- **WHEN** 用户发送 `/novel list`
- **THEN** 系统返回当前群聊可用的所有小说列表，标注当前激活的小说

#### Scenario: 用户删除小说
- **WHEN** 用户发送 `/novel delete <小说名>`
- **THEN** 系统删除指定小说及其所有数据，若删除的是当前激活小说则自动取消激活

### Requirement: 小说创作 Agent 调用
系统 SHALL 通过 `tool_loop_agent` 调用 LLM Agent 进行小说创作，在创作过程中提供内部 Tool 供 Agent 使用。

#### Scenario: 用户发起写故事
- **WHEN** 用户发送 `/novel write <创作要求>`
- **THEN** 系统调用 `tool_loop_agent`，将创作要求作为 prompt，携带小说管理 Tool 集合，Agent 自主完成创作并返回结果

#### Scenario: 用户修正故事
- **WHEN** 用户发送 `/novel revise <修正要求>`
- **THEN** 系统调用 `tool_loop_agent`，将修正要求作为 prompt，Agent 根据要求修正已有内容

### Requirement: 小说内部 Tool 集
系统 SHALL 在 Agent 写小说时提供以下内部 Tool，供 LLM 自主调用以管理小说结构化数据：

1. **角色画像管理 Tool**：创建、查询、修改、删除角色（姓名、性格、外貌、背景等）
2. **角色关系管理 Tool**：创建、查询、修改、删除角色间关系（关系类型、描述等）
3. **事件管理 Tool**：创建、查询、修改、删除事件（事件名、时间线位置、描述、涉及角色等）
4. **剧情大纲管理 Tool**：创建、查询、修改、删除剧情大纲（章节规划、情节走向等）
5. **章节内容管理 Tool**：创建、查询、修改章节正文内容

#### Scenario: Agent 在创作中调用角色画像 Tool
- **WHEN** Agent 判断需要创建或查询角色信息
- **THEN** Tool 正确执行并返回结果，数据持久化到存储中

#### Scenario: Agent 在创作中调用剧情大纲 Tool
- **WHEN** Agent 判断需要规划或查询剧情走向
- **THEN** Tool 正确执行并返回结果，数据持久化到存储中

### Requirement: 小说阅读与查询
系统 SHALL 提供阅读小说、列出章节、对小说提问的功能。

#### Scenario: 用户阅读小说
- **WHEN** 用户发送 `/novel read [章节号]`
- **THEN** 若指定章节号则返回该章节内容，否则返回当前激活小说的概览信息

#### Scenario: 用户列出章节
- **WHEN** 用户发送 `/novel chapters`
- **THEN** 系统返回当前激活小说的所有章节列表

#### Scenario: 用户对小说提问
- **WHEN** 用户发送 `/novel ask <问题>`
- **THEN** 系统调用 `tool_loop_agent`，携带小说上下文和内部 Tool，Agent 基于小说内容回答问题

### Requirement: 结束创作会话
系统 SHALL 提供结束当前创作会话的功能。

#### Scenario: 用户结束创作
- **WHEN** 用户发送 `/novel stop`
- **THEN** 系统保存当前状态并结束创作会话，返回已保存提示

### Requirement: 群聊激活小说互斥
系统 SHALL 保证一个群聊（session）同时只能激活一本小说。

#### Scenario: 群聊已激活一本小说时创建新小说
- **WHEN** 群聊已有激活小说，用户发送 `/novel create <新小说名>`
- **THEN** 新小说创建成功并自动切换为激活状态，原小说变为非激活

#### Scenario: 群聊无激活小说时执行需要激活小说的指令
- **WHEN** 群聊无激活小说，用户发送 `/novel write`、`/novel read` 等指令
- **THEN** 系统提示用户需要先创建或切换一本小说

### Requirement: 数据持久化存储
系统 SHALL 使用 AstrBot KV 存储管理元数据（群聊激活状态映射），使用 JSON 文件存储小说详细数据，存储路径遵循 `data/plugin_data/astrbot_plugin_novel_generator/` 规范。

#### Scenario: 数据持久化
- **WHEN** 插件执行任何写操作
- **THEN** 数据被正确写入持久化存储，重启后可恢复

#### Scenario: 存储结构
- **WHEN** 查看存储目录
- **THEN** 结构如下：
  - KV 存储：`session_id -> active_novel_id` 映射
  - JSON 文件：`data/plugin_data/astrbot_plugin_novel_generator/novels/{novel_id}.json`，每个文件包含一本小说的完整数据（元信息、角色、关系、事件、大纲、章节）

### Requirement: Plugin Page 可视化管理
系统 SHALL 提供一个 Plugin Page，可视化展示和管理所有小说内容。

#### Scenario: 用户打开 Page
- **WHEN** 用户在 AstrBot WebUI 插件详情页点击进入 Page
- **THEN** 页面展示所有小说列表，支持查看、编辑小说的各类数据

#### Scenario: Page 展示小说详情
- **WHEN** 用户在 Page 中选择一本小说
- **THEN** 页面展示该小说的角色、关系、事件、大纲、章节等所有结构化数据

#### Scenario: Page 编辑小说数据
- **WHEN** 用户在 Page 中修改角色、关系、事件、大纲、章节等数据
- **THEN** 修改通过后端 API 持久化，下次查看时生效

### Requirement: 插件配置
系统 SHALL 通过 `_conf_schema.json` 提供可配置项。

#### Scenario: 用户配置插件
- **WHEN** 用户在 WebUI 中修改插件配置
- **THEN** 配置项包括：默认最大 Agent 步数、默认工具调用超时时间、小说数据存储路径等

## MODIFIED Requirements

无

## REMOVED Requirements

无
