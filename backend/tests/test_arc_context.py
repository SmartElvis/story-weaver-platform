"""Tests for the dependency-free arc-context helpers."""

from app.services.arc_context import format_milestones_progress, format_arc_plan


def test_format_milestones_progress_renders_entries_in_order():
    entries = [
        (1, [{"milestone": "主角逃離廢墟", "impact": "開啟旅程"}]),
        (2, [{"milestone": "結識夥伴塔娜"}]),
    ]
    block = format_milestones_progress(entries)
    assert block.startswith("## 已達成的情節里程碑")
    assert "- 第1章：主角逃離廢墟" in block
    assert "- 第2章：結識夥伴塔娜" in block
    # Ascending order preserved.
    assert block.index("第1章") < block.index("第2章")


def test_format_milestones_progress_empty_returns_empty_string():
    assert format_milestones_progress([]) == ""
    assert format_milestones_progress([(1, []), (2, None)]) == ""


def test_format_milestones_progress_tolerates_plain_strings_and_blanks():
    entries = [
        (3, ["純字串里程碑", {"milestone": "  "}, {"milestone": "有效里程碑"}]),
    ]
    block = format_milestones_progress(entries)
    assert "- 第3章：純字串里程碑" in block
    assert "- 第3章：有效里程碑" in block
    # Blank milestone entries are skipped.
    assert block.count("第3章") == 2


_PLAN = {
    "theme": "復仇與救贖",
    "central_conflict": "主角與殺父仇人的對決",
    "total_chapters": 20,
    "acts": [
        {"name": "第一幕：鋪陳", "chapter_range": "1-5", "goal": "建立動機"},
        {"name": "第二幕：對抗", "chapter_range": "6-15", "goal": "節節敗退"},
    ],
    "milestones": [
        {"id": "m1", "title": "逃離廢墟", "target_chapter": 1, "status": "achieved"},
        {"id": "m2", "title": "中點反轉", "target_chapter": 8, "status": "pending"},
        {"id": "m3", "title": "決戰", "target_chapter": 18, "status": "pending"},
    ],
    "character_arcs": [
        {"name": "林默", "want": "復仇", "need": "放下"},
    ],
}


def test_format_arc_plan_renders_core_and_progress():
    block = format_arc_plan(_PLAN)
    assert "故事藍圖" in block
    assert "復仇與救贖" in block
    assert "切勿提前解決" in block
    assert "約 20 章" in block
    assert "已達成 1 / 共 3" in block
    assert "林默" in block


def test_format_arc_plan_highlights_current_act():
    block = format_arc_plan(_PLAN, chapter_number=8)
    assert "當前所處階段：第二幕：對抗" in block


def test_format_arc_plan_lists_upcoming_milestones_ordered():
    block = format_arc_plan(_PLAN, chapter_number=8)
    # Achieved milestone is not listed as upcoming.
    assert "逃離廢墟" not in block.split("接下來待達成的里程碑")[1]
    # Pending milestones appear, nearest target first.
    idx_mid = block.index("中點反轉")
    idx_final = block.index("決戰")
    assert idx_mid < idx_final


def test_format_arc_plan_empty_returns_empty_string():
    assert format_arc_plan(None) == ""
    assert format_arc_plan({}) == ""
    assert format_arc_plan({"milestones": []}) == ""
