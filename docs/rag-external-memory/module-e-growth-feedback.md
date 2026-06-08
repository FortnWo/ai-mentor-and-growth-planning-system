# 板块 E 升级方案：成长反馈

**状态**：已定稿（讨论确认「基本满意」）  
**定稿日期**：2026-06-08

## 一、定位

**板块 E = 成长轨迹的汇总展示层 + UKL 成长切片生产者 + 反馈生成消费者。**

| 角色 | 说明 |
| --- | --- |
| **汇总展示** | 时间线、统计、成就；实体以 `growth_records` / `growth_summaries` 为 canonical |
| **UKL 生产者** | 写入时异步沉淀 `growth_journal`、`growth_pattern`、`weekly_narrative`、`milestone_achievement` 等切片 |
| **反馈消费者** | 周总结、即时微反馈生成时，`UKL.assemble_context(scene=feedback)` 拉多维度私域上下文 |

- **不引入**外部公共 RAG 主线（最多后期极轻量静态话术，非标准 RAG）
- **不做**向量检索（特定场景由 A 等板块门控实现）
- **继承**双轨模型：MySQL 实体 = 真相；UKL = 带 `ref_id` 的叙事/模式投影

## 二、设计原则

| 原则 | 说明 |
| --- | --- |
| **写入时沉淀** | 记录/里程碑/打卡入库后异步提炼 UKL 切片，UKL 越用越厚 |
| **总线变薄、UKL 变厚** | 事件只传「发生了什么」最小 payload；语义汇聚在 UKL ingest |
| **私域组装** | 反馈质量取决于 `scene=feedback` 上下文，非外部知识库 |
| **手写与打卡分权** | 手写偏反思与情绪；打卡偏执行证据；画像补强需**汇总后**再喂 D |
| **即时 + 周期** | 除周总结外，里程碑/关键节点有即时微反馈 |
| **与 B 划界** | B 产 `execution_feedback`（规划用）；E 产 `growth_pattern`（复盘/陪伴/画像用） |

## 三、架构分工

```text
用户手写 / B 打卡回写 / C·B 里程碑完成
        │
        ▼
growth_records（实体 canonical）
        │
        ├─► 前端时间线 / 统计（现有能力保留）
        │
        └─► UKL ingest（异步）
                ├─ growth_journal（单条投影，带 ref）
                ├─ growth_pattern（跨条/跨周模式，批量沉淀）
                ├─ milestone_achievement（主节点 + 子节点软聚合完成）
                └─ weekly_narrative（周复盘叙事，周期产出）

UKL.assemble_context(scene=feedback)
        │
        ├─► 周总结生成
        ├─► 即时微反馈
        └─►（供 D 读取）growth_pattern → 非聊天画像补强主来源之一
```

| 角色 | 职责 |
| --- | --- |
| **E（成长板块）** | 成长记录汇总、反馈生成、成长类 UKL 切片生产 |
| **UKL** | 多切片 ingest、统一存储、按 `scene=feedback` 组装 |
| **B / C** | 打卡回写、里程碑完成触发；语义经 UKL 汇聚，不散落各处 JOIN |
| **D** | 订阅 `growth_pattern`（批量），作为非聊天画像补强主要来源之一 |

**写入模式**：多水流汇入单池（与 D 方案一致）。  
**读取模式**：反馈生成经 UKL 索取，不裸拼 title 列表。

## 四、成长记录与里程碑（实体层）

### 写入触发

| 触发 | 实体动作 |
| --- | --- |
| B item 完成（自动打卡） | `growth_record`，`record_type=action_plan`，保留现有 `action_plan_service` 回写 |
| 用户手写记录 | `growth_record`，`record_type=manual` |
| **主里程碑完成**（plan → main 指挥链，见 [module-b-action-plan.md](./module-b-action-plan.md)） | `growth_record`，`record_type=milestone`，`source_ref_id=breakdown_id` |
| **子节点软聚合为 completed**（B 方案已定） | 同上 + UKL `milestone_achievement` |

> **现状缺口**：`GrowthRecordType.MILESTONE` 已定义，但全仓库尚无写入路径；升级后由 C/B 完成事件触发，经 UKL ingest 统一处理，避免各处零碎 JOIN。

### 与 B 子节点软聚合的衔接

子节点状态由关联 items 软聚合推导（B 方案）。当子节点变为 `completed` 时：

```text
1. 写 milestone 类型 growth_record（source_ref_id = 子节点 breakdown_id）
2. UKL ingest milestone_achievement 切片
3. 可选：触发即时微反馈（见第六节）
4. 发布 ON_MILESTONE_REACHED（精简 payload）
```

主里程碑完成时同样走上述路径，`milestone_level` 区分 `main` / `child`。

## 五、UKL 切片（E 生产）

| 切片类型 | 更新时机 | 内容示例 | 主要消费者 |
| --- | --- | --- | --- |
| `growth_journal` | 每条 record 入库后 | 单条叙事投影 + `ref_id`（record / plan_item / breakdown） | E 组装、审计 |
| `growth_pattern` | **批量**（日终 / 周总结前 / 达 N 条打卡阈值） | 反复主题、情绪趋势、拖延模式、周末低谷 | **D 画像**、E 反馈、A 叙事 |
| `milestone_achievement` | 主/子节点完成时 | 「完成预习阶段子目标 B1」+ goal/breakdown ref | E 反馈、前端成就 |
| `weekly_narrative` | 周总结生成后回写 UKL | 本周故事线，第二人称 | A Tier1、下期对比 |

**规矩**（继承 C）：切片必须带 `source_module`、`ref_type`、`ref_id`；禁止 duplicate 可从 `growth_records` JOIN 的全文。

### 写入时沉淀 pipeline（异步）

```text
growth_record 入库
    → growth_journal ingest（即时）
    → 累计计数 / 定时器
    → 达阈值 → growth_pattern 批量更新
    → 若里程碑 → milestone_achievement ingest
    → 通知 D（仅 pattern 批量更新后，非逐条打卡）
```

## 六、反馈形态：周期 + 即时

| 类型 | 触发 | 组装 | 说明 |
| --- | --- | --- | --- |
| **周总结** | 用户请求 / 定时（升级现有 `growth_summary_service`） | `scene=feedback` 全量组装 | 有证据的复盘 + 下周小步建议 |
| **即时微反馈** | 主/子里程碑达成；可选高 salience 手写记录 | 轻量 `scene=feedback` 或专用 `scene=instant_feedback` | 短 LLM 祝贺/点睛，强化陪伴感 |

周总结单独力度偏小；即时微反馈与周期复盘 **互补**，共同构成 E 的反馈双轨。

### `assemble_context(scene=feedback)` 拉取范围

| 来源 | 用途 |
| --- | --- |
| **当周 `growth_records`（实体）** | 事实证据 |
| **UKL `growth_pattern`** | 跨周对比、反复卡点 |
| **UKL `milestone_achievement`** | 本周成就语义（含子节点） |
| **UKL profile snapshot（D 产）** | 语气与个性化 |
| **UKL `breakdown_summary` / `goal_intent`（C/A 产）** | 阶段语境 |
| **UKL `execution_feedback`（B 产）** | 执行证据，与叙事互补 |

### 叙事 + 锚点（继承 C）

周总结叙事可压缩，但须同批保留结构化锚点：

- `goal_refs[]`
- `breakdown_refs[]`
- `critical_moments[]`

避免摘要丢关联；结构数据从实体 JOIN，UKL 补「为什么、情绪、趋势」。

## 七、与 D 的画像补强

**`growth_pattern` 作为 D 的非聊天主要信号来源之一**（与 B 的 `execution_feedback` 并列、侧重不同）。

### 批量补强策略（应对「手写少、打卡多」）

```text
单条打卡入库
  → 写 growth_journal（UKL）
  → 不立即触发 D 画像更新

达阈值后（例如：本周打卡 ≥ N 条 / 日终批量 / 周总结前）
  → 汇总打卡 pattern + 同期手写记录
  → 产出/更新 growth_pattern 切片
  → 通知 D 订阅 ingest（或 D 定时拉取 pattern）
  → D 修正 traits（拖延、坚持度、情绪倾向等）
```

| 信号类型 | 画像补强权重 | 说明 |
| --- | --- | --- |
| 用户手写反思 | 高 | 主观、语义丰富 |
| 批量打卡 pattern | 中 | 行为证据，需汇总去噪 |
| 单条自动打卡 | 低 | **不逐条触发 D** |

避免打卡 flood 稀释画像，也避免手写过少导致补强失效。详见 [module-d-profile.md](./module-d-profile.md) 扩展职责。

## 八、与 B 的 `execution_feedback` 划界

| 切片 | 生产者 | 消费者侧重 | 内容 |
| --- | --- | --- | --- |
| `execution_feedback` | **B** | C/B 规划、planning_loop | 完成率、子节点进度、负载 |
| `growth_pattern` | **E** | E 反馈、**D 画像**、A 叙事 | 情绪、反思主题、跨周趋势、反复卡点 |

E 生成反馈时 **两者都读**；生产职责 **不混**。  
B 告诉系统「计划执行得怎样」；E 告诉用户「这段时间对你意味着什么」。

## 九、事件总线（变薄后的契约）

总线 payload 保持精简；语义补全在 UKL ingest：

```yaml
# ON_GROWTH_UPDATED（已有，扩展可选字段）
record_id: <int>
record_type: manual | action_plan | milestone
source_type: <enum>
goal_id: <int>?      # 可选，由 ingest 补全亦可
breakdown_id: <int>?

# ON_MILESTONE_REACHED（新增建议）
breakdown_id: <int>
goal_id: <int>
milestone_level: main | child
plan_id: <int>?
```

`growth_cycle_orchestrator` 中 `_on_growth_updated` / `_on_action_completed` 从「仅打日志」升级为 **转发 UKL ingest**（实现阶段）；D 订阅 `growth_pattern` 批量更新事件。

## 十、分阶段落地

| 阶段 | 能力 |
| --- | --- |
| **E1** | `assemble_context(scene=feedback)` 升级周总结；`growth_journal` ingest |
| **E2** | 主/子节点 milestone 实体写入 + `milestone_achievement`；即时微反馈 |
| **E3** | `growth_pattern` 批量沉淀；对接 D 非聊天补强；`weekly_narrative` 回写 UKL |

## 十一、与现有代码的关系

| 现有 | 升级后 |
| --- | --- |
| `growth_summary_service` 标题列表拼 prompt | UKL `scene=feedback` 多切片组装 |
| `GrowthRecordType.MILESTONE` 无写入 | C/B 完成 → milestone record + UKL 切片 |
| `ON_GROWTH_UPDATED` 仅打日志 | UKL ingest 订阅；D 订阅 pattern（批量） |
| B item 完成 → `growth_record` | 保留；子节点软聚合 completed → milestone 路径 |
| `growth_daily_aggregate` 统计 | 保留；可与 `growth_pattern` 互补 |

## 十二、明确不做

- 外部公共 RAG 知识库（主线）
- E 内向量检索
- 每条打卡即时触发 D 画像更新
- UKL 内 duplicate 全量 `growth_records` 正文

## 十三、讨论记录摘要

- E 具有数据汇总属性；B/C 成果经事件同步，但仅靠总线 payload 信息不全 → UKL 统一汇聚
- 里程碑应对应 C 节点；子节点软聚合完成也应写入 milestone
- 不做外部 RAG；向量不在 E 范围
- 写入时沉淀，提升板块有机性；UKL 越用越厚
- 手写少、打卡多 → **汇总后**再补强 D，非逐条
- 周总结 + 即时微反馈双轨
- `growth_pattern` 为 D 非聊天补强主要来源，非常必要
- UKL 建立后总线变薄、数据流规整，效率更高
