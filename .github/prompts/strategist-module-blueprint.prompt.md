---
name: "军师-模块蓝图生成"
description: "生成模块级架构蓝图，覆盖数据库、后端分层、前端结构、数据流与 AI 调用链。"
argument-hint: "请输入模块目标、当前现状、约束条件、优先级与期望交付时间"
agent: "AI Mentor Chief Strategist"
tools: [read, search, web]
---
请基于用户输入与当前仓库结构，输出一个可执行的模块蓝图。

输出要求：
1. 需求核心：目标、范围、约束、验收标准。
2. 模块蓝图：数据库、Model/Schema/Service/Router、前端 API/Store/View/Component、AI 调用链。
3. 数据流图（文字版）：按步骤描述从用户动作到结果回显。
4. 任务拆解：P0/P1/P2、依赖关系、里程碑。
5. 风险与优化建议：至少 3 条，含替代路线。

注意事项：
- 输出中文。
- 不输出实现代码。
- 术语与命名尽量对齐项目现有结构。
