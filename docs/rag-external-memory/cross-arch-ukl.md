# 跨板块统一架构：用户知识层（UKL）

**状态**：初稿（五板块定稿后汇总；实现前可迭代）  
**汇总日期**：2026-06-08

本文档汇总 [D](./module-d-profile.md)、[A](./module-a-chat.md)、[C](./module-c-goal-breakdown.md)、[B](./module-b-action-plan.md)、[E](./module-e-growth-feedback.md) 五板块方案中对 UKL 的共识，作为后续设计与实现的统一参考。

## 一、定位

**UKL（User Knowledge Layer，用户知识层 / 外置记忆层）= 用户私域知识的统一汇聚、存储与按场景组装出口。**

| 原则 | 说明 |
| --- | --- |
| **双轨模型** | MySQL 业务实体 = canonical（Source of Truth）；UKL 切片 = 带 `ref_id` 的投影/叙事/模式 |
| **多水流写入、单池存储、单出口读取** | 各板块为切片生产者；下游只调 `assemble_context`，不散落 JOIN |
| **总线变薄、UKL 变厚** | `event_bus` 传最小 payload；语义补全在 UKL ingest |
| **叙事 + 锚点** | 叙事省 token；不可丢失约束用结构化锚点同批写入 |
| **向量非第一版必需** | A3 仅事实条目子集；E/D/C/B 第一版不依赖向量 |

```text
┌───────── 写入方（多水流）─────────┐
│ D: profile                          │
│ A: episodic_narrative, goal_intent  │
│ C: breakdown_summary, anchors       │
│ B: workload_snapshot, execution_fb  │
│ E: growth_journal, pattern, milestone│
└──────────────┬──────────────────────┘
               ▼
        UKL ingest（规范化 + provenance）
               ▼
        UKL store（按 user_id + slice_type）
               ▼
        assemble_context(scene, ...)
               ▼
┌───────── 读取方 ─────────────────────┐
│ A: chat / instant_feedback           │
│ C: breakdown / planning_loop         │
│ B: action_plan / planning_loop       │
│ E: feedback / instant_feedback       │
│ D: growth_pattern（批量，非 assemble）│
└──────────────────────────────────────┘
```

## 二、切片类型注册表

所有切片须带：`user_id`、`slice_type`、`source_module`、`ref_type`、`ref_id`（可空但需有理由）、`updated_at`、`payload`。

| slice_type | 生产者 | 主要消费者 | 说明 |
| --- | --- | --- | --- |
| `profile` | D | A/B/C/E 全场景 | traits + `portrait_snapshot`；D 生产逻辑，UKL 存储与对外读 |
| `episodic_narrative` | A | A Tier1 | 跨 session 长期叙事 |
| `goal_intent` | A | C `breakdown` | 聊天中目标的动机叙事 + `goal_id` ref |
| `breakdown_summary` | C | B/E/A | 拆解路径叙事，非整树 |
| `breakdown_anchors` | C | B/C | `critical_constraints[]` 等结构化锚点 |
| `workload_snapshot` | B | C/B | 跨目标负载 |
| `execution_feedback` | B | C/B `planning_loop` | 完成率、子节点进度 |
| `plan_summary` | B（可选） | A/E | 计划叙事，非全量 items |
| `growth_journal` | E | E | 单条成长记录投影 |
| `growth_pattern` | E | **D**、E、A | 跨周模式；D 非聊天补强主来源 |
| `milestone_achievement` | E | E、前端 | 主/子里程碑成就 |
| `weekly_narrative` | E | A、E | 周复盘故事线 |
| `memory_fact`（A3） | A | A Tier2 向量 | 事实条目元数据 |

**冗余规矩**（继承 C）：禁止在无 `ref_id` 时 duplicate 可从实体 JOIN 的字段。

## 三、`assemble_context` 场景枚举

统一入口（概念 API）：

```text
assemble_context(
    user_id: int,
    scene: str,
    *,
    goal_id: int | None = None,
    main_breakdown_id: int | None = None,
    plan_id: int | None = None,
    session_id: int | None = None,
    query: str | None = None,   # A Tier2 门控用
) -> ContextBundle
```

`ContextBundle` 含：`narrative_blocks[]`、`anchors{}`、`entity_hints{}`（提示下游 JOIN 哪些实体）、`token_budget_hint`。

### 场景与拉取切片

| scene | 触发方 | 拉取切片（默认集） |
| --- | --- | --- |
| `chat` | A 每轮 | profile、episodic_narrative、growth_pattern（轻量）、session 本地摘要（非 UKL） |
| `breakdown` | C `ON_GOAL_DETECTED` / 刷新 | profile、goal_intent、workload_snapshot；刷新时 + execution_feedback |
| `action_plan` | B `ON_GOAL_BREAKDOWN` / 重生成 | profile、breakdown_summary、breakdown_anchors、workload_snapshot、execution_feedback |
| `planning_loop` | 执行失败后联合重规划 | breakdown + action_plan 全部 + 相关叙事 |
| `feedback` | E 周总结 | profile、growth_pattern、milestone_achievement、execution_feedback、breakdown_summary、goal_intent、当周实体 ref |
| `instant_feedback` | E 里程碑/高 salience 事件 | profile、milestone_achievement、轻量 goal_intent |

**实体层并行读取**：`scene=breakdown` 须 JOIN `user_goals`；`scene=action_plan` 须 JOIN `goal_breakdowns` 树；UKL 不替代实体结构数据。

## 四、Ingest 契约

### 写入 API（概念）

```text
ukl.ingest(
    user_id: int,
    slice_type: str,
    source_module: str,      # profile_service | chat_service | ...
    ref_type: str | None,    # goal | breakdown | record | plan | ...
    ref_id: int | None,
    payload: dict,
    metadata: dict | None,
) -> slice_id
```

### 触发来源

| 来源 | 典型事件 | ingest 责任 |
| --- | --- | --- |
| D 画像更新 | `ON_PROFILE_UPDATED` | profile 切片 |
| A 聊天固化 | `ON_CHAT_MESSAGE`（异步） | episodic_narrative、goal_intent、memory_fact |
| C 拆解完成 | `ON_GOAL_BREAKDOWN` | breakdown_summary、breakdown_anchors |
| B 计划/打卡 | `ON_ACTION_GENERATED`、`ON_ACTION_COMPLETED` | workload_snapshot、execution_feedback |
| E 成长/里程碑 | `ON_GROWTH_UPDATED`、`ON_MILESTONE_REACHED` | growth_journal、growth_pattern、milestone_achievement |

`growth_cycle_orchestrator` **保留业务流程编排**；UKL ingest 作为 **并行订阅者**，不替代 orchestrator。

### 批量与异步

- ingest **不阻塞**用户请求主路径（聊天回复、打卡确认等）
- `growth_pattern`、trait 演进类更新 **批量**触发
- 失败重试 + 死信日志（实现阶段）

## 五、与 `event_bus` 的关系

### 变薄后的事件 payload 示例

```yaml
ON_CHAT_MESSAGE:
  session_id, message_id, role

ON_PROFILE_UPDATED:
  user_id, profile_version

ON_GOAL_DETECTED:
  goal_id, trace_id

ON_GOAL_BREAKDOWN:
  goal_id, breakdown_root_ids[]

ON_ACTION_COMPLETED:
  plan_id, goal_id, item_id, breakdown_id?

ON_GROWTH_UPDATED:
  record_id, record_type, source_type

ON_MILESTONE_REACHED:    # 建议新增
  breakdown_id, goal_id, milestone_level: main|child
```

语义字段（叙事、模式、约束）**不在 payload 中重复**，由 UKL ingest 查实体 + LLM 提炼后写入切片。

## 六、存储方案（第一版）

**推荐**：MySQL 扩展表，与现有栈一致，避免过早引入独立向量库。

| 表/结构 | 用途 |
| --- | --- |
| `ukl_slice`（概念） | 切片主表：user_id、slice_type、ref、payload JSON、provenance、version |
| `ukl_slice_latest`（概念，可选） | 每 user+slice_type+ref 的最新版指针，加速 assemble |
| `chat_session_summary` | A 专用，session 级滚动摘要（可不进 ukl_slice） |
| `memory_embedding`（A3） | 事实条目向量 |

规模上来后：`memory_embedding` 可迁 Chroma/pgvector 等，UKL 接口不变。

## 七、过渡期双写策略

| 阶段 | 行为 |
| --- | --- |
| **T0（现状）** | 各 service 直读 `user_profile`、`growth_records` 等 |
| **T1** | UKL 落地；写入双写（业务表 + UKL）；读取 **优先 UKL**，失败回退旧路径 |
| **T2** | 全部 `assemble_context` 切换完成；`portrait_summary` 对外权威迁 UKL |
| **T3** | 移除直读 fallback；事件仅驱动 ingest |

**权威约定**：对外 context 以 **UKL 为准**；实体表为准的是 **结构化业务数据**（目标、树、计划项、成长记录原文）。

## 八、分阶段落地（跨板块）

| 阶段 | 范围 | 能力 |
| --- | --- | --- |
| **UKL0** | 基础设施 | `ukl_slice` 表、ingest、assemble 骨架；`scene=chat` 仅 profile |
| **UKL1** | A1 + D | profile ingest；`scene=chat` + session 摘要 |
| **UKL2** | C + B | breakdown 切片；`scene=breakdown`、`scene=action_plan` |
| **UKL3** | B2 + E1 | execution 切片；`scene=feedback`；growth_journal |
| **UKL4** | E2/E3 + A2 | milestone、growth_pattern、叙事固化；D 批量补强 |
| **UKL5** | A3 | memory_fact 向量；Tier2 门控 |

各板块文档中的 **X1/X2/X3** 阶段嵌入上述 UKL 阶段，实现时统一排期。

## 九、权限与隔离

- 所有切片 **按 `user_id` 严格隔离**
- ingest/assemble 在 service 层校验当前用户
- 管理员只读工具走独立 audit 路径（现有 `admin_tool_service` 模式）

## 十、公共 RAG（全局，非 UKL 核心）

公共知识库与 UKL **并列**，不写入用户私域池：

- A4 正式接入；A2 可选手动导入接口
- E 不用公共 RAG 主线
- 合规话术库可作为全局静态配置，非标准 RAG

## 十一、相关文档索引

| 板块 | 文档 | UKL 角色 |
| --- | --- | --- |
| D | [module-d-profile.md](./module-d-profile.md) | profile 生产者 |
| A | [module-a-chat.md](./module-a-chat.md) | episodic 生产者；chat 最大消费者 |
| C | [module-c-goal-breakdown.md](./module-c-goal-breakdown.md) | breakdown 生产者；breakdown 消费者 |
| B | [module-b-action-plan.md](./module-b-action-plan.md) | execution 生产者；action_plan 消费者 |
| E | [module-e-growth-feedback.md](./module-e-growth-feedback.md) | growth 生产者；feedback 消费者 |

## 十二、实现进度

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| **UKL0** | 已完成 | `ukl_slice` 表、`ukl_service` ingest/assemble、`UKL_ENABLED` profile 双写 |
| **UKL1** | 已完成 | `chat_session_summary`、`build_chat_context`、聊天主路径注意力打包 |
| **UKL2** | 已完成 | `scene=breakdown`/`action_plan`、拆解 UKL 切片、行动计划覆盖校验 |
| **UKL3** | 已完成 | execution 切片 ingest、`scene=feedback`、growth_journal、周总结 UKL 路径 |
| **UKL4** | 已完成 | milestone 实体与 `milestone_achievement`、`growth_pattern`/`weekly_narrative`、A2 叙事固化、D 批量补强、`scene=instant_feedback` |
| **UKL5** | 已完成 | `memory_fact` 切片 + `memory_embedding` 表、异步事实抽取、Tier2 门控向量检索、`[相关事实记忆]` prompt 注入 |

## 十三、待实现时细化的项

- `ukl_slice` 精确 schema 与索引策略
- `ContextBundle` 序列化格式与 token 预算算法
- `growth_pattern` 批量阈值配置（env / system_config）
- `ON_MILESTONE_REACHED` 注册与 orchestrator 关系
- ingest 失败重试、切片版本作废规则
- A3 `memory_embedding` 选型
