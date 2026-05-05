from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class GoalBreakdownNode(BaseModel):
    """表示目标拆解树中的一个节点"""
    id: int
    title: str
    description: str | None = None
    level: int
    sequence: int
    status: str
    due_date: str | None = None
    children: list["GoalBreakdownNode"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoalBreakdownTree(BaseModel):
    """目标拆解树结构"""
    goal_id: int
    title: str
    description: str | None = None
    root_nodes: list[GoalBreakdownNode] = Field(default_factory=list)


class GoalCreate(BaseModel):
    """创建目标的请求体"""
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    priority: str = Field(default="medium")
    target_date: str | None = None  # ISO 8601 date format: YYYY-MM-DD


class GoalUpdate(BaseModel):
    """更新目标的请求体"""
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    status: str | None = None
    priority: str | None = None
    target_date: str | None = None


class GoalRead(BaseModel):
    """目标读取响应"""
    id: int
    user_id: int
    title: str
    description: str | None = None
    status: str
    priority: str
    target_date: date | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoalDetailRead(GoalRead):
    """包含拆解树的目标详情"""
    breakdowns: GoalBreakdownTree


class GoalBreakdownCreate(BaseModel):
    """创建目标拆解节点的请求体"""
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    parent_id: int | None = None
    level: int = 0
    sequence: int = 0
    status: str = "pending"
    due_date: str | None = None


class GoalBreakdownRead(BaseModel):
    """目标拆解节点读取响应"""
    id: int
    goal_id: int
    parent_id: int | None = None
    title: str
    description: str | None = None
    level: int
    sequence: int
    status: str
    due_date: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
