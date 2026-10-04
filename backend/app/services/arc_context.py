"""Arc-context helpers for long-form coherence.

These pure functions turn per-chapter extraction data into prompt blocks that
give the generation agents a sense of the *whole* story arc, not just the last
chapter. Keeping them dependency-free (no ORM imports) lets them be unit-tested
in isolation.

The motivating problem: with only local context (previous ending + flat
summaries), the model writes episodic "and then, and then" fiction. Surfacing
the milestones already achieved — plus an explicit "advance toward the next
beat, do not resolve the main conflict yet" instruction — gives each chapter a
job within the larger arc.
"""

from __future__ import annotations

from typing import Iterable


def format_milestones_progress(entries: Iterable[tuple[int, list]]) -> str:
    """Build a "已達成里程碑" prompt block from ``(chapter_number, milestones)`` pairs.

    ``milestones`` is the ``plot_milestones`` list from a chapter's extraction
    result (each item normally a dict with at least a ``milestone`` key, but
    plain strings are tolerated). Returns an empty string when there is nothing
    to show, so callers can append the result unconditionally.
    """
    lines: list[str] = []
    for chapter_number, milestones in entries:
        for m in milestones or []:
            if isinstance(m, dict):
                text = m.get("milestone") or ""
            else:
                text = str(m)
            text = (text or "").strip()
            if text:
                lines.append(f"- 第{chapter_number}章：{text}")
    if not lines:
        return ""
    return "## 已達成的情節里程碑（前面各章）\n" + "\n".join(lines)


def _short(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _parse_range(range_str) -> tuple[int, int] | None:
    """Parse a chapter-range string like ``"1-5"`` into ``(lo, hi)`` ints."""
    if not isinstance(range_str, str):
        return None
    parts = range_str.replace("~", "-").split("-")
    nums = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            nums.append(int(digits))
    if not nums:
        return None
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums), max(nums)


def format_arc_plan(plan: dict | None, chapter_number: int | None = None) -> str:
    """Render a structured arc plan into a compact prompt block.

    Highlights the act the current chapter sits in (when ``chapter_number`` is
    given) and lists the next few pending milestones, so the generation agents
    always know where this chapter falls in the overall arc and what it should
    push toward. Returns an empty string when the plan carries no usable
    structure, so callers can append the result unconditionally.
    """
    if not isinstance(plan, dict):
        return ""

    milestones = plan.get("milestones") or []
    theme = (plan.get("theme") or "").strip()
    conflict = (plan.get("central_conflict") or "").strip()
    if not milestones and not theme and not conflict:
        return ""

    lines: list[str] = ["## 故事藍圖（整體弧線）"]
    if theme:
        lines.append(f"核心主題：{_short(theme, 80)}")
    if conflict:
        lines.append(f"核心衝突（切勿提前解決）：{_short(conflict, 100)}")
    total = plan.get("total_chapters")
    if isinstance(total, int) and total > 0:
        lines.append(f"預估總章數：約 {total} 章")

    # Which act the current chapter sits in.
    if chapter_number is not None:
        for act in plan.get("acts") or []:
            if not isinstance(act, dict):
                continue
            bounds = _parse_range(act.get("chapter_range"))
            if bounds and bounds[0] <= chapter_number <= bounds[1]:
                act_name = act.get("name") or ""
                goal = act.get("goal") or ""
                lines.append(f"當前所處階段：{act_name}（{_short(goal, 60)}）")
                break

    achieved = [m for m in milestones if isinstance(m, dict) and m.get("status") == "achieved"]
    pending = [m for m in milestones if isinstance(m, dict) and m.get("status") != "achieved"]
    lines.append(f"里程碑進度：已達成 {len(achieved)} / 共 {len(milestones)}")

    if pending:
        # Show the nearest upcoming milestones first.
        def _target(m: dict) -> int:
            t = m.get("target_chapter")
            return t if isinstance(t, int) else 10**9

        upcoming = sorted(pending, key=_target)[:5]
        lines.append("接下來待達成的里程碑：")
        for m in upcoming:
            target = m.get("target_chapter")
            target_txt = f"目標第{target}章" if isinstance(target, int) else "目標章節未定"
            title = _short(m.get("title") or "（未命名）", 40)
            lines.append(f"- [{target_txt}] {title}")

    arcs = plan.get("character_arcs") or []
    if arcs:
        arc_lines = []
        for arc in arcs[:6]:
            if not isinstance(arc, dict):
                continue
            name = arc.get("name") or "未命名"
            want = _short(arc.get("want") or "", 30)
            need = _short(arc.get("need") or "", 30)
            if want or need:
                arc_lines.append(f"- {name}：想要 {want}，實則需要 {need}")
        if arc_lines:
            lines.append("主要角色弧線：")
            lines.extend(arc_lines)

    return "\n".join(lines)
