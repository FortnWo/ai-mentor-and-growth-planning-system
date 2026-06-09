# RAG / 外置记忆 — 分模块升级方案

本目录存放与各功能板块讨论后定稿的升级方案，供后续设计与实现参考。

| 板块 | 文档 | 状态 |
| --- | --- | --- |
| D 画像提取与更新 | [module-d-profile.md](./module-d-profile.md) | 已定稿 |
| A 聊天问答 | [module-a-chat.md](./module-a-chat.md) | 已定稿 |
| B 行动计划 | [module-b-action-plan.md](./module-b-action-plan.md) | 已定稿 |
| C 目标拆解 | [module-c-goal-breakdown.md](./module-c-goal-breakdown.md) | 已定稿 |
| E 成长反馈 | [module-e-growth-feedback.md](./module-e-growth-feedback.md) | 已定稿 |
| 跨板块统一架构（UKL） | [cross-arch-ukl.md](./cross-arch-ukl.md) | 初稿（五板块汇总） |

## UKL 落地进度摘要

| 阶段 | 状态 |
| --- | --- |
| UKL0–UKL4 | 已完成并验收 |
| UKL5 | 实现已完成；embedding 配置与端到端验收待补 |

## 总体原则

- **标准 RAG**：文档切分 → 向量化 → 检索 → 注入 Prompt → 生成（适用于公共知识、可解释引用）
- **RAG 思想（外置记忆）**：对话与用户数据处理后写入用户私域知识库，生成时按需组装上下文
- **用户知识层（UKL）**：多切片写入、统一存储、按场景动态组装；各业务板块为切片生产者或数据源
