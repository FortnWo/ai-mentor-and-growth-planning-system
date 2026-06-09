SLICE_TYPE_PROFILE = "profile"
SLICE_TYPE_GOAL_INTENT = "goal_intent"
SLICE_TYPE_BREAKDOWN_SUMMARY = "breakdown_summary"
SLICE_TYPE_BREAKDOWN_ANCHORS = "breakdown_anchors"
SLICE_TYPE_WORKLOAD_SNAPSHOT = "workload_snapshot"
SLICE_TYPE_EXECUTION_FEEDBACK = "execution_feedback"
SLICE_TYPE_GROWTH_JOURNAL = "growth_journal"
SLICE_TYPE_MILESTONE_ACHIEVEMENT = "milestone_achievement"
SLICE_TYPE_GROWTH_PATTERN = "growth_pattern"
SLICE_TYPE_WEEKLY_NARRATIVE = "weekly_narrative"
SLICE_TYPE_EPISODIC_NARRATIVE = "episodic_narrative"

SCENE_CHAT = "chat"
SCENE_BREAKDOWN = "breakdown"
SCENE_ACTION_PLAN = "action_plan"
SCENE_FEEDBACK = "feedback"
SCENE_INSTANT_FEEDBACK = "instant_feedback"

REF_TYPE_USER = "user"
REF_TYPE_GOAL = "goal"
REF_TYPE_MAIN_BREAKDOWN = "main_breakdown"
REF_TYPE_BREAKDOWN = "breakdown"
REF_TYPE_RECORD = "record"
REF_TYPE_PLAN = "plan"

SOURCE_MODULE_PROFILE = "profile_service"
SOURCE_MODULE_BREAKDOWN = "breakdown_service"
SOURCE_MODULE_ACTION_PLAN = "action_plan_service"
SOURCE_MODULE_GROWTH = "growth_record_service"
SOURCE_MODULE_MILESTONE = "milestone_service"
SOURCE_MODULE_CHAT = "chat_context_service"
SOURCE_MODULE_PATTERN = "ukl_pattern_service"
SOURCE_MODULE_NARRATIVE = "ukl_narrative_service"

PROFILE_FIELD_NAMES = (
    "interests",
    "skills",
    "goals",
    "study_habits",
    "personality",
    "preferences",
)

CONSTRAINT_HINT_KEYWORDS = (
    "每天",
    "每周",
    "每月",
    "必须",
    "小时",
    "截止",
    "之前",
    "以内",
)

FEEDBACK_MAX_ACTIVE_GOALS = 5
