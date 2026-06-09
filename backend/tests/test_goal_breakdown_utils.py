from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus
from app.models.user import User
from app.services.goal_breakdown_utils import (
    is_three_level_goal_wrapper,
    list_main_breakdown_ids,
    list_main_breakdown_nodes,
)


def _add_breakdown(db, goal_id, title, parent_id=None, level=0, sequence=0):
    node = GoalBreakdown(
        goal_id=goal_id,
        parent_id=parent_id,
        title=title,
        description="",
        level=level,
        sequence=sequence,
        status=GoalBreakdownStatus.PENDING.value,
    )
    db.add(node)
    db.flush()
    return node


def test_two_level_tree_uses_roots_as_main(db_session):
    user = User(username="u1", email="u1@x.com", password_hash="h", role="user", is_active=True)
    db_session.add(user)
    db_session.flush()
    goal = Goal(user_id=user.id, title="G", priority="medium")
    db_session.add(goal)
    db_session.flush()

    main = _add_breakdown(db_session, goal.id, "Phase 1", level=0)
    _add_breakdown(db_session, goal.id, "Step 1", parent_id=main.id, level=1, sequence=0)
    _add_breakdown(db_session, goal.id, "Step 2", parent_id=main.id, level=1, sequence=1)
    db_session.commit()

    roots = [main]
    assert is_three_level_goal_wrapper(db_session, roots) is False
    mains = list_main_breakdown_nodes(db_session, goal.id)
    assert [m.id for m in mains] == [main.id]


def test_three_level_tree_uses_children_as_main(db_session):
    user = User(username="u2", email="u2@x.com", password_hash="h", role="user", is_active=True)
    db_session.add(user)
    db_session.flush()
    goal = Goal(user_id=user.id, title="Learn Frontend", priority="medium")
    db_session.add(goal)
    db_session.flush()

    wrapper = _add_breakdown(db_session, goal.id, "Learn Frontend", level=0)
    pillar_a = _add_breakdown(db_session, goal.id, "HTML/CSS", parent_id=wrapper.id, level=1, sequence=0)
    pillar_b = _add_breakdown(db_session, goal.id, "JavaScript", parent_id=wrapper.id, level=1, sequence=1)
    _add_breakdown(db_session, goal.id, "HTML5", parent_id=pillar_a.id, level=2, sequence=0)
    _add_breakdown(db_session, goal.id, "ES6", parent_id=pillar_b.id, level=2, sequence=0)
    db_session.commit()

    assert is_three_level_goal_wrapper(db_session, [wrapper]) is True
    mains = list_main_breakdown_nodes(db_session, goal.id)
    assert {m.id for m in mains} == {pillar_a.id, pillar_b.id}
    assert list_main_breakdown_ids(db_session, goal.id) == [pillar_a.id, pillar_b.id]
