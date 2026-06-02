# Details

Date : 2026-06-02 21:31:00

Directory c:\\Users\\Fortune\\OneDrive\\Desktop\\辰桑\\dev\\FortnWo\\ai-mentor-and-growth-planning-system\\backend\\app

Total : 57 files,  4642 codes, 49 comments, 1188 blanks, all 5879 lines

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [backend/app/__init__.py](/backend/app/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [backend/app/core/__init__.py](/backend/app/core/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [backend/app/core/bootstrap.py](/backend/app/core/bootstrap.py) | Python | 36 | 0 | 5 | 41 |
| [backend/app/core/config.py](/backend/app/core/config.py) | Python | 56 | 0 | 11 | 67 |
| [backend/app/core/database.py](/backend/app/core/database.py) | Python | 17 | 0 | 7 | 24 |
| [backend/app/core/domain_events.py](/backend/app/core/domain_events.py) | Python | 38 | 0 | 9 | 47 |
| [backend/app/core/event_bus.py](/backend/app/core/event_bus.py) | Python | 99 | 0 | 21 | 120 |
| [backend/app/core/security.py](/backend/app/core/security.py) | Python | 69 | 0 | 31 | 100 |
| [backend/app/core/ws_manager.py](/backend/app/core/ws_manager.py) | Python | 34 | 5 | 9 | 48 |
| [backend/app/main.py](/backend/app/main.py) | Python | 130 | 1 | 27 | 158 |
| [backend/app/models/__init__.py](/backend/app/models/__init__.py) | Python | 33 | 0 | 2 | 35 |
| [backend/app/models/action_plan.py](/backend/app/models/action_plan.py) | Python | 96 | 0 | 21 | 117 |
| [backend/app/models/chat.py](/backend/app/models/chat.py) | Python | 38 | 0 | 15 | 53 |
| [backend/app/models/domain_event.py](/backend/app/models/domain_event.py) | Python | 23 | 0 | 10 | 33 |
| [backend/app/models/goal.py](/backend/app/models/goal.py) | Python | 72 | 0 | 24 | 96 |
| [backend/app/models/growth_aggregate.py](/backend/app/models/growth_aggregate.py) | Python | 14 | 0 | 9 | 23 |
| [backend/app/models/growth_record.py](/backend/app/models/growth_record.py) | Python | 50 | 0 | 19 | 69 |
| [backend/app/models/growth_summary.py](/backend/app/models/growth_summary.py) | Python | 12 | 0 | 7 | 19 |
| [backend/app/models/profile.py](/backend/app/models/profile.py) | Python | 86 | 0 | 30 | 116 |
| [backend/app/models/user.py](/backend/app/models/user.py) | Python | 96 | 0 | 19 | 115 |
| [backend/app/models/user_trait.py](/backend/app/models/user_trait.py) | Python | 32 | 0 | 11 | 43 |
| [backend/app/routers/__init__.py](/backend/app/routers/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [backend/app/routers/action_plan.py](/backend/app/routers/action_plan.py) | Python | 141 | 0 | 26 | 167 |
| [backend/app/routers/auth.py](/backend/app/routers/auth.py) | Python | 17 | 0 | 8 | 25 |
| [backend/app/routers/chat.py](/backend/app/routers/chat.py) | Python | 78 | 2 | 22 | 102 |
| [backend/app/routers/goal.py](/backend/app/routers/goal.py) | Python | 169 | 3 | 29 | 201 |
| [backend/app/routers/growth_record.py](/backend/app/routers/growth_record.py) | Python | 116 | 3 | 20 | 139 |
| [backend/app/routers/health.py](/backend/app/routers/health.py) | Python | 6 | 0 | 4 | 10 |
| [backend/app/routers/info.py](/backend/app/routers/info.py) | Python | 33 | 0 | 10 | 43 |
| [backend/app/routers/profile.py](/backend/app/routers/profile.py) | Python | 24 | 0 | 10 | 34 |
| [backend/app/routers/user.py](/backend/app/routers/user.py) | Python | 83 | 0 | 20 | 103 |
| [backend/app/routers/ws.py](/backend/app/routers/ws.py) | Python | 37 | 3 | 8 | 48 |
| [backend/app/schemas/__init__.py](/backend/app/schemas/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [backend/app/schemas/action_plan.py](/backend/app/schemas/action_plan.py) | Python | 35 | 0 | 14 | 49 |
| [backend/app/schemas/auth.py](/backend/app/schemas/auth.py) | Python | 10 | 0 | 5 | 15 |
| [backend/app/schemas/chat.py](/backend/app/schemas/chat.py) | Python | 52 | 1 | 32 | 85 |
| [backend/app/schemas/goal.py](/backend/app/schemas/goal.py) | Python | 80 | 0 | 24 | 104 |
| [backend/app/schemas/growth_record.py](/backend/app/schemas/growth_record.py) | Python | 56 | 0 | 18 | 74 |
| [backend/app/schemas/growth_summary.py](/backend/app/schemas/growth_summary.py) | Python | 13 | 0 | 6 | 19 |
| [backend/app/schemas/profile.py](/backend/app/schemas/profile.py) | Python | 61 | 0 | 21 | 82 |
| [backend/app/schemas/user.py](/backend/app/schemas/user.py) | Python | 75 | 0 | 22 | 97 |
| [backend/app/services/__init__.py](/backend/app/services/__init__.py) | Python | 19 | 0 | 2 | 21 |
| [backend/app/services/action_plan_service.py](/backend/app/services/action_plan_service.py) | Python | 604 | 0 | 111 | 715 |
| [backend/app/services/ai_service.py](/backend/app/services/ai_service.py) | Python | 75 | 0 | 31 | 106 |
| [backend/app/services/auth_service.py](/backend/app/services/auth_service.py) | Python | 21 | 0 | 8 | 29 |
| [backend/app/services/breakdown_service.py](/backend/app/services/breakdown_service.py) | Python | 92 | 0 | 23 | 115 |
| [backend/app/services/chat_service.py](/backend/app/services/chat_service.py) | Python | 293 | 12 | 76 | 381 |
| [backend/app/services/goal_service.py](/backend/app/services/goal_service.py) | Python | 183 | 4 | 50 | 237 |
| [backend/app/services/growth_record_service.py](/backend/app/services/growth_record_service.py) | Python | 433 | 14 | 68 | 515 |
| [backend/app/services/growth_service.py](/backend/app/services/growth_service.py) | Python | 75 | 0 | 19 | 94 |
| [backend/app/services/growth_summary_service.py](/backend/app/services/growth_summary_service.py) | Python | 45 | 1 | 9 | 55 |
| [backend/app/services/info_service.py](/backend/app/services/info_service.py) | Python | 10 | 0 | 8 | 18 |
| [backend/app/services/plan_service.py](/backend/app/services/plan_service.py) | Python | 77 | 0 | 25 | 102 |
| [backend/app/services/profile_service.py](/backend/app/services/profile_service.py) | Python | 195 | 0 | 53 | 248 |
| [backend/app/services/user_service.py](/backend/app/services/user_service.py) | Python | 164 | 0 | 64 | 228 |
| [backend/app/workflows/__init__.py](/backend/app/workflows/__init__.py) | Python | 2 | 0 | 3 | 5 |
| [backend/app/workflows/growth_cycle_orchestrator.py](/backend/app/workflows/growth_cycle_orchestrator.py) | Python | 237 | 0 | 48 | 285 |

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)