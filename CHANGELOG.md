# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-06-09

### Added

- Web 管理页面全面重写，新增概览、角色、关系、事件、大纲、章节、世界观七个 Tab
- Web API：支持从管理页面创建、删除小说（`POST /novels/create`、`POST /novels/<id>/delete`）
- Web API：支持编辑小说名称和故事梗概（`POST /novels/<id>/update`）
- Web API：支持下载小说 TXT 文件，可下载全本或单章（`GET /novels/<id>/download`）
- 概览面板：展示角色、关系、事件、大纲、章节数量统计及总字数
- 关系和事件中角色 ID 自动解析为名称显示
- 角色选择使用下拉菜单替代文本输入
- 大纲支持树形层级展示
- 世界观设定按分类分组展示
- 章节列表显示状态标签（草稿/审阅/定稿）和字数统计
- 小说列表支持搜索过滤

## [0.1.4] - 2026-06-08

### Added

- 优化小说存储和读取逻辑，改进章节内容处理
- 优化角色创建提示词

## [0.1.3] - 2026-06-07

### Added

- 添加文件发送支持，优化跨容器部署的文件处理逻辑
- 添加中文别名支持（`/小说` 等同 `/novel`），优化指令可用性
- 添加会话隔离模式，支持按用户或群组隔离小说数据

## [0.1.2] - 2026-06-06

### Added

- 增强小说管理功能，添加章节内容长度计算和重编号功能
- 添加章节内容长度属性（`content_length`）
- 更新插件元数据，提升描述和版本信息；添加插件 logo
- 更新章节正文写入策略，调整分段追加字数范围为 1500-2500 字
- 添加创作和思考提示语

### Fixed

- 修复无法下载小说的问题

## [0.1.1] - 2026-06-03

### Added

- 增强章节管理：支持排序权重（`order`）、自定义标签（`label`）、番外标记（`is_extra`）
- 支持章节移动（`move`）和整体重排（`reorder`）操作
- 添加只读工具类和系统提示，支持 `/novel ask` 查询和搜索功能
- 重构小说存储和工具类，支持更灵活的内容加载与保存
- 添加分段发送功能，支持自定义每段最大字符数和发送延迟
- 添加小说系统提示词配置（`novel_system_prompt`）和搜索功能
- 添加 LLM provider 配置选项
- 添加世界观设定功能（`WorldSetting`）并完善小说数据模型

### Changed

- 重构项目代码，使用 dataclass 替代 Pydantic Field
- 合并修订指令到写入指令

## [0.1.0] - 2026-05-29

### Added

- 初始化小说生成插件项目结构
- 基于 AstrBot Agent 的小说创作核心功能
