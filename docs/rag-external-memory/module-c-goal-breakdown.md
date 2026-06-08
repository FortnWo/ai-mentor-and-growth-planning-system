# 板块 C 升级方案：目标拆解

**状态**：已定稿（讨论确认「基本满意」）  
**定稿日期**：2026-06-04

## 一、定位

**板块 C = 目标路径的结构化分解**，输入端依赖 **UKL 私域上下文 + 事件总线**，输出为 **树形拆解实体**（`goal_breakdowns`）。

- **不引入**外部专业知识库 RAG（对结构化树形输出收益有限）
- **核心升级**：用 `UKL.assemble_context(scene=breakdown)` 替代当前单薄的 profile 数组拼接
- **与 B 形成规划链**：C 定战略路径，B 定战术排程；B 切片通过 UKL 按场景组装，而非单一归属 C 或 B

## 二、设计原则

| 原则 | 说明 |
| --- | --- |
| **双轨模型** | MySQL 实体 = 唯一事实来源；UKL 切片 = 带 `ref_id` 的投影/叙事 |
| **事件驱动触发** | 沿用 `growth_cycle_orchestrator` 链路，UKL 不改变「何时拆」 |
| **叙事 + 锚点** | UKL 摘要提高效率，结构化锚点保留不可丢失的约束 |
| **B/C 场景化组装** | B 切片不判定单一消费者，由 UKL `scene` 决定拉取组合 |
| **树在实体层** | 完整拆解树存 `goal_breakdowns`；UKL 不 duplicate 整树 |

## 三、与现有流水线的关系

```text
ON_CHAT_MESSAGE
    → 画像抽取（D）→ ON_PROFILE_UPDATED
    → 检测目标 → 创建 Goal → ON_GOAL_DETECTED

ON_GOAL_DETECTED
    → UKL.assemble_context(scene=breakdown, goal_id)   ← 升级点
    → LLM 生成拆解 JSON
    → breakdown_service 解析入库（树实体）
    → 写入 UKL breakdown_summary + 锚点
    → ON_GOAL_BREAKDOWN

ON_GOAL_BREAKDOWN
    → B 生成行动计划（见板块 B）
```

**替换点**：`growth_cycle_orchestrator._build_goal_breakdown_prompt` 从「goal + profile 数组」改为调用 UKL 组装器 + 读取 Goal 实体 canonical 字段。

## 四、C 的职责边界

### 消费（读取）

| 来源 | 内容 |
| --- | --- |
| **Goal 实体** | `title`、`description`、`priority`、`target_date`（canonical） |
| **UKL `scene=breakdown`** | profile 切片、goal_intent（A）、workload_snapshot（B）、本 goal 的 execution_feedback（刷新时） |

### 生产（写入 UKL）

| 切片类型 | 内容 | 说明 |
| --- | --- | --- |
| `breakdown_summary` | 阶段逻辑、路径意图的叙事摘要 | 非整树；供 B/A/E 补充上下文 |
| `breakdown_anchors` | `goal_id`、`critical_constraints[]`、`dependency_notes[]`、`capacity_hint` | 与摘要同批写入；不可丢失约束 |

### 明确不做

- 公共专业知识库 RAG
- UKL 内 duplicate 完整 `goal_breakdowns` 树
- 跨板块实体统筹（归实体层 + UKL 服务）
- UI / JSON 规范化（另案处理）

## 五、双轨模型与冗余控制

```text
业务实体层（Source of Truth）          UKL 切片层（LLM 上下文投影）
─────────────────────────────          ─────────────────────────────
user_goals                             goal_intent（叙事 + goal_id ref）
goal_breakdowns（完整树）               breakdown_summary + breakdown_anchors
action_plans / items                   workload_snapshot、execution_feedback
```

**规矩**：UKL 切片必须带 `source_module`、`ref_type`、`ref_id`；可从实体 JOIN 的字段禁止在无 `ref_id` 时重复存储。

**与 `profile.goals[]` 的关系**：profile 中为检测信号；落地后以 `goal_id` 为锚，C/B/E 均引用实体而非 profile 数组。

## 六、叙事摘要与信息保留

摘要用于省 token，但 **不替代 canonical**。

| 层级 | 存储 | 不可丢失信息 |
| --- | --- | --- |
| 实体层 | 完整树、节点 id/层级 | 结构、精确引用 |
| UKL 叙事 | 阶段关系、意图、节奏 | — |
| UKL 锚点 | `critical_constraints` 等结构化字段 | 用户明确约束、依赖、能力提示 |

**摘要生成约束**：

1. 用户明确约束（时间上限、截止日期）→ 写入 `critical_constraints`，不依赖叙事
2. 树明细由实体提供；摘要只描述阶段逻辑
3. 摘要带 `entity_updated_at` / 版本号；实体变更则作废重算
4. LLM 调用：结构从 DB，UKL 补「为什么、难点、节奏」

## 七、C 与 B 的规划链（B 切片消费）

C 定 **战略分解**（几步、顺序、粒度）；B 定 **战术排程**（频率、日期、具体任务）。  
「眼高手低」可能来自 C 结构过满或 B 排程过满，需两端协同。

### B 切片类型（UKL 内，由 B 生产，按场景消费）

| 切片 | 主要生产者 | C 消费时机 | B 消费时机 |
| --- | --- | --- | --- |
| `workload_snapshot` | B 汇总 | **首次拆解**、刷新拆解 | 首次生成计划、重生成计划 |
| `execution_feedback` | B 打卡/完成数据 | **刷新拆解** | 重生成计划 |
| `breakdown_summary` | C | — | prompt 补充（树仍以实体为准） |

### UKL 组装场景

| 场景 | 触发 | 拉取切片 |
| --- | --- | --- |
| `scene=breakdown` | `ON_GOAL_DETECTED`、用户刷新拆解 | profile、goal_intent、workload_snapshot；刷新时 + execution_feedback |
| `scene=action_plan` | `ON_GOAL_BREAKDOWN`、重生成计划 | profile、breakdown 实体、execution_feedback、workload_snapshot |
| `scene=planning_loop` | 执行失败后联合重规划 | 上述全部 + 相关叙事 |

**首次拆解**：B 本 goal 尚无执行史，但 **必须** 含 `workload_snapshot`（跨目标负载），避免忽视并行目标。

**B 生成计划时**：拆解树从 `goal_breakdowns` 实体读取（含 `breakdown_ref` id）；`breakdown_summary` 仅作叙事补充。

## 八、分阶段落地

| 阶段 | 能力 |
| --- | --- |
| **C1** | `assemble_context(scene=breakdown)` 替代 profile 拼接；Goal 实体不变 |
| **C2** | 拆解完成后写入 `breakdown_summary` + `breakdown_anchors` |
| **C3** | 刷新拆解接入 `execution_feedback`；与 B 共用 `planning_loop` 场景 |

## 九、与现有代码的关系

| 现有 | 升级后 |
| --- | --- |
| `_on_goal_detected` + `_build_goal_breakdown_prompt` | UKL assemble + Goal 实体 |
| `breakdown_service.apply_breakdown_for_goal` | 保留（树解析入库） |
| `profile_service.get_profile_for_user` 直接拼 prompt | 改为 UKL profile 切片 |
| `event_bus` / orchestrator | 保留触发链 |

## 十、留待板块 B 讨论

- `workload_snapshot`、`execution_feedback` 的字段与更新时机
- `scene=planning_loop` 是否在执行失败后自动触发「先改树再改计划」
- 与 C 直接相关的已知 bug

## 十一、讨论记录摘要

- 外部 RAG 对 C 价值有限；中心在 UKL + 事件总线
- 双轨模型控制冗余；实体 canonical，UKL 投影
- 叙事摘要 + 结构化锚点防信息丢失
- B 切片按 UKL 场景组装，C/B 作为规划链一并考虑
- 首次拆解需 cross-goal workload；刷新拆解需 execution feedback
