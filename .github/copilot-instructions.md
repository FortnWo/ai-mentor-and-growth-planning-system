# Project Guidelines

## Mission
本项目目标是构建可长期陪伴用户成长的 AI 导师系统。
系统核心闭环是：聊天 -> 画像 -> 目标 -> 计划 -> 成长 -> 再画像。

## Core Product Goals
1. 理解用户是谁（用户画像）
2. 理解用户想做什么（目标拆解）
3. 告诉用户应该怎么做（行动计划）
4. 记录用户做了什么（成长记录）
5. 通过聊天持续更新画像与目标（AI 驱动）

## Collaboration Modes
- 军师模式：当用户要求需求分析、架构设计、数据库设计、API 设计、模块拆解、技术路线或综合 Prompt 时，优先进行方案设计与结构化交付。
- 工程模式：当用户明确要求实现、修改代码、修复问题、补测试时，执行工程落地并保持与设计一致。
- 当用户意图不清晰时，先用最小问题澄清，再继续执行。

## Architecture Baseline
- 后端采用分层结构：models、schemas、services、routers。
- 前端采用页面与 API 分层：views、api、stores、router、components。
- AI 调用链分三层：聊天层、目标层、行动层。

## Database Baseline
现有表：users、chat_sessions、chat_messages。
规划新增表：user_extended_profiles、goals、goal_breakdowns、action_plans、growth_records。

## Delivery Expectations
- 输出优先中文，内容结构化且可执行。
- 涉及跨模块变更时，明确数据流、接口契约、异常处理、验收标准。
- 涉及军师交付时，默认输出模块蓝图、综合 Prompt、任务拆解、风险建议。

## Source Of Truth
- [项目总设计文档](../项目总设计文档.md)
- [军师指南](../军师指南.md)
- [工程师指南](../工程师指南.md)
- [README](../README.md)
