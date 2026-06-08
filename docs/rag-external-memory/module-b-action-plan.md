# 板块 B 升级方案：行动计划

**状态**：已定稿（讨论确认「相对满意」）  
**定稿日期**：2026-06-04

## 一、定位

**板块 B = 在主里程碑粒度上，将 C 的直接子节点落地为可执行任务**。

- 以 C 的拆解树为输入，生成 `action_plans` / `action_plan_items`
- **继承 C 方案**：双轨模型、UKL 私域组装、规划链；**不做**外部专业知识库 RAG
- 核心升级在 **输入端（UKL + 实体）** 与 **子节点相关性**；保留现有两层结构与主节点指挥链

## 二、设计原则

| 原则 | 说明 |
| --- | --- |
| **继承 C** | 同一套 UKL assemble、叙事+锚点、规划链；非平行新体系 |
| **结构不变** | 一主节点一计划；`breakdown_ref` 指向主节点或直接子节点 |
| **主节点指挥** | plan 全量 items 聚合 → plan 状态 → main_breakdown 状态（保留） |
| **子节点软联动** | 子节点状态由关联 items **自动推导**，非 1:1 刚性绑定 |
| **私域知识** | `scene=action_plan` 拉取 UKL；B 生产 `workload_snapshot` / `execution_feedback` |

## 三、与 C 的规划链

```text
ON_GOAL_BREAKDOWN
    → prepare_action_plans_for_goal（每根节点一篇 plan）
    → UKL.assemble_context(scene=action_plan, goal_id, main_breakdown_id)
    → LLM 生成 plan JSON
    → 解析入库 + 子节点覆盖校验
    → 写入/更新 UKL execution 相关切片
    → ON_ACTION_GENERATED / ON_ACTION_COMPLETED
```

详见 [module-c-goal-breakdown.md](./module-c-goal-breakdown.md) 中 `workload_snapshot`、`execution_feedback`、`planning_loop` 场景。

## 四、保留不变的机制

| 机制 | 说明 |
| --- | --- |
| 一主节点一计划 | `prepare_action_plans_for_goal` 按 `parent_id IS NULL` 的根节点创建 plan |
| 两层引用 | items 的 `breakdown_id` / `breakdown_ref` → 主节点或直接子节点 |
| 主节点状态指挥 | `_sync_aggregate_plan_and_main_status`：全部 items → plan → **main_breakdown** |
| 事件总线 | `ON_GOAL_BREAKDOWN` 触发；完成时 `ON_ACTION_COMPLETED` 等 |

## 五、已知问题与对策

### 现象

生成的行动计划 **语义上** 更像服务主里程碑，与 **直接子节点** 意图弱相关，出现「一套目标、两套脱节子内容」。

### 根因（讨论共识）

- 子节点在 prompt 中 **描述薄**，缺少 UKL 路径语义（`breakdown_summary` / `breakdown_anchors`）
- 模型未稳定遵守 `breakdown_ref` 与子节点的对应关系
- （非结构问题）现 prompt 已列 secondary 节点，但上下文重心偏主节点

### 对策（B1 输入 + 输出）

**输入**

- 用 `UKL.assemble_context(scene=action_plan, goal_id, main_breakdown_id)` 替代裸 profile 拼接
- 实体侧：Goal + `main_node` + **direct children** `secondary_nodes`（结构不改）
- 从 UKL 拉取该主里程碑相关的 `breakdown_summary`、`breakdown_anchors`，充实各子节点分工与约束

**输出**

- Prompt 强化：每个 secondary 应有可辨认的任务簇，`breakdown_ref` 必须指向对应子节点 id
- **生成后轻量校验**：每个 secondary id 至少 1 个 item 引用（合并冗余时的例外规则实现时再定）；未覆盖则重试或失败告警

**不做**

- 拆解树多层扁平化
- 为修 bug 而改变主节点指挥链

## 六、子节点与 item 的联动（软聚合）

### 原则

- **不完全不联动**：子节点应反映其下任务进度
- **不完全刚性 1:1**：允许多 item 服务同一子节点；单 item 异常不必然拖垮子节点
- **主节点仍为指挥官**：主节点状态 **只** 跟整篇 plan 的 items 聚合，不改为「须等每个子节点都 completed」

### 关联范围

对每个直接子节点 `S`（同一 `main_breakdown_id` 下的 plan）：

```text
linked_items = plan 内 breakdown_id == S.id 的所有 items
```

若无子节点，则 items 可指向主节点 id。

### 子节点状态规则（启发式）

| linked_items | 子节点 `goal_breakdowns.status` |
| --- | --- |
| 空 | `pending` |
| 全部 `completed` | `completed` |
| 部分 `completed` | `in_progress` |
| 有 item 但无一 completed | `pending` |

**刻意不做（第一版）**

- 单 item 跳过/失败 → 子节点标 `failed`
- 关键任务权重、手动覆盖子节点状态（可后期扩展）

### 主节点（不变）

```text
plan 状态 ← 该 plan 下全部 items
main_breakdown 状态 ← plan 状态
```

### 触发时机

item 状态变更（含完成回写成长记录）时：

```text
1. 重算受影响的直接子节点状态
2. 执行现有 plan + main 聚合（_sync_aggregate_plan_and_main_status）
```

### 与 UKL

`execution_feedback` 切片可包含 **按子节点的完成率**（如「子节点 B1：3/5 items」），供 C 刷新拆解与 B 重生成使用。

## 七、UKL 职责

### 消费（`scene=action_plan`）

| 切片 | 用途 |
| --- | --- |
| profile | 个性化排程 |
| `breakdown_summary` / `breakdown_anchors`（C 产） | 子节点语义与约束 |
| `workload_snapshot` | 跨目标负载，避免排太满 |
| `execution_feedback` | 重生成时参考历史执行 |

### 生产

| 切片 | 更新时机 |
| --- | --- |
| `workload_snapshot` | 计划生成/变更、活跃任务聚合 |
| `execution_feedback` | item 完成/跳过/逾期、子节点软聚合后 |

可选：`plan_summary` 叙事（非全量 items），供 A/E 引用。

### 明确不做

- 外部专业知识库 RAG
- UKL 内 duplicate 全量 `action_plan_items`

## 八、双轨与冗余（继承 C）

- **实体层**：`action_plans`、`action_plan_items` 为 canonical
- **UKL 层**：叙事摘要、执行反馈、负载快照；带 `ref_type` / `ref_id` 指向 `goal_id`、`plan_id`、`main_breakdown_id`

## 九、分阶段落地

| 阶段 | 能力 |
| --- | --- |
| **B1** | `assemble_context(scene=action_plan)`；子节点覆盖校验；修生成相关性 |
| **B2** | 子节点软聚合状态；`execution_feedback` / `workload_snapshot` 写入 UKL |
| **B3** | 与 C 共用 `scene=planning_loop`（执行失败后联合重规划） |

## 十、与现有代码的关系

| 现有 | 升级后 |
| --- | --- |
| `_build_action_plan_prompt_for_main` | UKL assemble + 实体（main + secondary） |
| `_sync_aggregate_plan_and_main_status` | 保留；前增加子节点软聚合 |
| `profile_service.get_profile_for_user` 直拼 | 改为 UKL profile 切片 |
| item 完成 → growth_record | 保留；增加子节点状态重算 |

## 十一、明确不做（另案）

- UI 展示、JSON 规范化细节
- 外部 RAG 知识库
- 拆解树层级改造

## 十二、讨论记录摘要

- B 与 C 同构：UKL 私域、无外部 RAG，逻辑继承 C
- Bug：计划与子节点语义弱相关 → UKL 输入 + 覆盖校验，不改两层结构
- 主节点指挥链保留；子节点状态由关联 items **软聚合** 自动推导
- 向量、公共 RAG 不在本板块范围
