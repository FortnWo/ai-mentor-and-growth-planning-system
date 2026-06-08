# 板块 D 升级方案：画像提取与更新

**状态**：已定稿（讨论确认「满意」）  
**定稿日期**：2026-06-04

## 一、定位

**板块 D = 用户知识层（UKL）的「画像切片生产者」**，不是整个私域库的 owner。

- 负责从对话及关联信号中 **提炼、演进用户画像**
- 产出规范化切片， **提交给 UKL 统一存储与对外读取**
- **不消费 RAG**；为 A/B/C/E 的生成与 RAG 提供上游画像数据

## 二、架构分工

```text
聊天 / 手动画像编辑 ──► D（画像板块）──► UKL（用户知识层）──► A/B/C/E 下游
B/E 等领域事件 ──────►（未来反哺修正画像）     ▲
                                              │
                         多切片写入、统一读取、按场景组装
```

| 角色 | 职责 |
| --- | --- |
| **D（画像板块）** | 对话抽取、trait 演进、手动画像维护、`portrait_summary` **生产** |
| **UKL（独立知识层）** | 多切片 ingest、统一存储、provenance、**对外读取与场景组装** |
| **B / E 等** | 业务数据源；原始执行/成长数据写入 UKL（各自切片），并可作为 D 丰富画像的信号来源 |

**写入模式**：多水流汇入单池。  
**读取模式**：下游只经 UKL 索取，不直接散落读各业务表。

## 三、D 的具体职责

### 保留并强化

1. **对话画像抽取** — 聊天 → LLM 结构化 JSON → `UserProfile` 字段 + `UserTrait`（含 score、source、时间）
2. **用户主动维护** — 前端画像编辑 → 合并更新 → 同步 trait
3. **高密度用户快照生产** — 基于 traits 生成 `portrait_summary`（第二人称叙事，150–250 字）；**逻辑留在 D**
4. **提交 UKL** — 画像更新完成后，将 profile 切片推送至 UKL；D 不承担对外读取

### 扩展（相对现状）

5. **拓宽信号来源** — 除聊天外，接收 B（`execution_feedback`）、E（`growth_pattern`）等 UKL 切片，用于修正/补强画像；**E 的 `growth_pattern` 为非聊天主要信号来源之一**（见 [module-e-growth-feedback.md](./module-e-growth-feedback.md)）
6. **trait 演进策略** — 在 `merge_unique` 之上，逐步引入置信度、时间衰减、冲突标记
7. **批量补强，非逐条** — 打卡记录远多于手写时：单条打卡 **不** 触发 D 更新；达阈值后汇总打卡 pattern + 同期手写，再更新 traits

### 明确不做

- 全量用户私域库的统筹与存储 owner
- 跨切片冲突的最终裁决（归 UKL）
- 下游场景化 context 组装（归 UKL）
- 向量检索（本阶段不做；留待板块 A 讨论）

## 四、`portrait_summary` 分工

| 环节 | 归属 |
| --- | --- |
| 生成逻辑（traits → 叙事摘要） | **D** |
| 持久化存储（canonical 副本） | **UKL** |
| 对外读取（聊天/计划/反馈等） | **UKL** |

D 更新画像后：先完成生产 → 将 snapshot 作为 profile 切片的一部分写入 UKL。  
下游模块只从 UKL 读 snapshot，避免 D 与 UKL 双份数据不一致。

## 五、与现有代码的关系

| 现有能力 | 升级后角色 |
| --- | --- |
| `profile_service` 抽取 / merge / trait 同步 | 保留，作为 D 核心 |
| `portrait_summary`（`user_profile` 表） | 过渡期可保留；长期以 UKL 为对外权威源 |
| `get_profile_insights_for_user` | 前端展示可走 UKL；或 D 代理调用 UKL |
| `action_plan_service` 等直接读 profile | 逐步改为经 UKL `assemble_context(scene=plan)` |
| `event_bus` + `growth_cycle_orchestrator` | D 订阅 `growth_pattern` 批量更新（E 产）；B `execution_feedback` 作规划向信号；UKL 并行 ingest |

## 六、D → UKL 接口（概念层）

**写入示例**

```yaml
slice_type: profile
payload:
  traits: [{ type, key, score, confidence, source, observed_at }]
  snapshot: "你……（叙事摘要）"
  fields: { interests, skills, goals, study_habits, personality, preferences }
metadata:
  producer: profile_service
  updated_at: <datetime>
```

**下游读取**（由 UKL 提供，非 D）

```text
assemble_context(user_id, scene=chat|plan|breakdown|feedback)
```

## 七、风险与取舍

- **过渡期双写**：约定 UKL 为对外权威，避免读取分叉
- **D 仍依赖 LLM 抽取**：拓宽 B/E 信号可缓解「只从聊天来」的局限
- **UKL 尚未落地**：最小 ingest/read API 在跨板块架构轮次与 A 讨论时敲定

## 八、讨论记录摘要

- 初识：D 不适合整体接入 RAG，应作为用户私域库上游，供其他板块引用
- 抉择：在「D 扩容统筹」与「独立 UKL + D 为切片生产者」之间，选定 **方案二**
- 共识：`portrait_summary` 由 D 生产、UKL 存储与读取；UKL 本阶段不涉及向量
