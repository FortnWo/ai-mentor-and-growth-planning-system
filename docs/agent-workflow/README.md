# Agent Workflow

This directory defines the shared Markdown contract for semi-automatic collaboration between the strategist and engineer agents.

## Purpose

The strategist writes the task definition once.
The engineer reads the same document, executes the task, and writes back implementation status.
The user only intervenes when a decision is blocked or a scope conflict appears.

## Files

- `current-task.md`: live shared task sheet for the active task.
- `task-template.md`: reusable blank template for new tasks.

## Ownership Rules

- Strategist owns goals, scope, constraints, acceptance criteria, and decision records.
- Engineer owns implementation notes, validation results, and execution risks.
- The user owns final scope approval when the two agents need a decision.

## Status Flow

Draft -> Ready -> In Progress -> Blocked -> Done

## Writing Rules

- Keep headings stable so the other agent can parse the document reliably.
- Do not rewrite unrelated sections when updating progress.
- Put open questions in the blocker section instead of burying them in prose.
- When a decision is made, record it in the decision log before changing status.

## Recommended Use

1. The strategist fills a new task into `current-task.md`.
2. The strategist marks the task as `Ready`.
3. The engineer reads the same file, changes status to `In Progress`, and starts work.
4. The engineer appends validation and execution notes.
5. If blocked, the engineer records the blocker and waits for a decision.
6. After validation passes, the engineer marks the task `Done`.