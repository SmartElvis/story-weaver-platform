"""Behavioral tests for the agents, driven by a fake LLM.

These verify each agent's response handling: JSON parsing, safe fallbacks on
unparseable output, and post-processing constraints — without any network or
model access.
"""

import pytest

from app.agents.weaver import (
    Weaver,
    _format_style_controls,
    _clean_weaver_output,
    _looks_like_refusal,
    WeaverRefusalError,
)
from app.agents.chronicler import Chronicler, DEFAULT_REVIEW
from app.agents.stylist import Stylist, DEFAULT_STYLE_REVIEW
from app.agents.extractor import Extractor, DEFAULT_EXTRACTION
from app.agents.foreseer import Foreseer
from app.agents.editor_analyst import EditorAnalyst
from app.agents.profiler import Profiler
from app.agents.architect import Architect, _normalize_plan

from tests.conftest import make_agent


# ── Weaver ────────────────────────────────────────────────────────────────

_WEAVER_KWARGS = dict(
    direction="推進主線",
    style_features={"tone": {"overall_mood": "冷峻"}},
    style_guide="短句為主，善用感官描寫。",
    plot_context="",
    story_outline="主角踏上旅途。",
    previous_ending="",
    character_cards=[{"name": "林默"}],
    world_settings={"era": "近未來"},
    previous_chapters_summary="",
)


async def test_weaver_parses_content_and_tokens():
    weaver = make_agent(Weaver, '{"content": "夜色如墨。", "tokens_used": 42}')
    result = await weaver.write(**_WEAVER_KWARGS)
    assert result["content"] == "夜色如墨。"
    assert result["tokens_used"] == 42


async def test_weaver_falls_back_to_raw_content():
    weaver = make_agent(Weaver, "這是一段沒有 JSON 包裝的小說正文。")
    result = await weaver.write(**_WEAVER_KWARGS)
    assert result["content"] == "這是一段沒有 JSON 包裝的小說正文。"
    assert result["tokens_used"] > 0


def test_clean_weaver_output_valid_json():
    content, tokens = _clean_weaver_output('{"content": "夜色如墨。", "tokens_used": 42}')
    assert content == "夜色如墨。"
    assert tokens == 42


def test_clean_weaver_output_plain_prose():
    content, tokens = _clean_weaver_output("純粹的小說正文，沒有包裝。")
    assert content == "純粹的小說正文，沒有包裝。"
    assert tokens is None


def test_clean_weaver_output_fenced_json():
    raw = '```json\n{"content": "正文內容", "tokens_used": 7}\n```'
    content, tokens = _clean_weaver_output(raw)
    assert content == "正文內容"
    assert tokens == 7


def test_clean_weaver_output_truncated_fenced_json():
    # Model wrapped output in a code fence + JSON but got cut off mid-string
    # (no closing quote, brace, or fence). Must salvage the prose, not dump the
    # ```json / {"content": " scaffolding into the chapter body.
    raw = '```json\n{"content": "我築了一座城。城牆是用三十幾年的獨身澆築的'
    content, tokens = _clean_weaver_output(raw)
    assert content == "我築了一座城。城牆是用三十幾年的獨身澆築的"
    assert "```" not in content
    assert '"content"' not in content
    assert tokens is None


def test_clean_weaver_output_degenerate_empty():
    # Truncated right after the opening quote — nothing usable to recover.
    content, tokens = _clean_weaver_output('```json\n{\n  "content": "')
    assert content == ""
    assert tokens is None


async def test_weaver_strips_scaffolding_from_content():
    raw = '```json\n{"content": "畢文中第三次把菸灰彈進鋁罐裡。'
    weaver = make_agent(Weaver, raw)
    result = await weaver.write(**_WEAVER_KWARGS)
    assert result["content"] == "畢文中第三次把菸灰彈進鋁罐裡。"
    assert "```" not in result["content"]
    assert "content" not in result["content"]


async def test_weaver_prompt_contains_style_guide_not_examples():
    weaver = make_agent(Weaver, '{"content": "x", "tokens_used": 1}')
    await weaver.write(**_WEAVER_KWARGS)
    user_msg = weaver.llm.calls[0]["messages"][1]["content"]
    assert "風格指南" in user_msg
    assert "短句為主" in user_msg
    # the old raw-example section must be gone
    assert "風格範例" not in user_msg


def test_format_style_controls_buckets():
    text = _format_style_controls(
        {"narrative_pace": 10, "dialogue_style": 50, "description_density": 90}
    )
    assert "快節奏推進" not in text  # 10 is low, not high
    assert "緩慢細膩" in text          # narrative_pace low
    assert "自然平衡" in text          # dialogue_style mid
    assert "濃墨重彩" in text          # description_density high


def test_format_style_controls_empty():
    assert _format_style_controls({}) == ""
    assert _format_style_controls(None) == ""


# ── Weaver refusal detection ────────────────────────────────────────────────

_REFUSAL_TEXT = (
    "無法根據當前提供的資訊撰寫小說正文。本次任務缺少以下必要素材："
    "1. 故事大綱——無從得知情節方向。請補充完整的專案素材後重新提交。"
)


def test_looks_like_refusal_detects_refusal():
    assert _looks_like_refusal(_REFUSAL_TEXT) is True


def test_looks_like_refusal_passes_normal_prose():
    prose = "夜色如墨，他推開門，走進了雨中。街燈把影子拉得很長。" * 5
    assert _looks_like_refusal(prose) is False


def test_looks_like_refusal_treats_empty_as_failure():
    assert _looks_like_refusal("") is True
    assert _looks_like_refusal("   \n  ") is True


async def test_weaver_write_raises_on_refusal():
    weaver = make_agent(Weaver, _REFUSAL_TEXT)
    with pytest.raises(WeaverRefusalError):
        await weaver.write(**_WEAVER_KWARGS)


async def test_weaver_revise_keeps_draft_on_refusal():
    weaver = make_agent(Weaver, _REFUSAL_TEXT)
    result = await weaver.revise(
        current_content="原本的良好草稿。",
        logic_review={"issues": [{"type": "timeline"}]},
        style_review=None,
    )
    # A refusing revision must not erase the existing draft.
    assert result["content"] == "原本的良好草稿。"
    assert result["tokens_used"] == 0


# ── Chronicler ──────────────────────────────────────────────────────────────

async def test_chronicler_default_on_garbage():
    chronicler = make_agent(Chronicler, "not json")
    result = await chronicler.review(
        draft="d", outline="o", character_cards=[], world_settings={},
        previous_chapters_summary="", chapter_number=1,
    )
    assert result == DEFAULT_REVIEW
    # deepcopy: mutating result must not corrupt the module default
    result["issues"].append("x")
    assert DEFAULT_REVIEW["issues"] == []


async def test_chronicler_parses_issues():
    chronicler = make_agent(
        Chronicler,
        '{"issues": [{"type": "timeline"}], "severity": "high", "needs_revision": true}',
    )
    result = await chronicler.review(
        draft="d", outline="o", character_cards=[], world_settings={},
        previous_chapters_summary="", chapter_number=2,
    )
    assert result["needs_revision"] is True
    assert result["issues"][0]["type"] == "timeline"


# ── Stylist ───────────────────────────────────────────────────────────────

async def test_stylist_default_on_garbage():
    stylist = make_agent(Stylist, "```not json```")
    result = await stylist.review(draft="d", style_features={}, style_examples=[])
    assert result == DEFAULT_STYLE_REVIEW


async def test_stylist_needs_revision_derived_from_score():
    stylist = make_agent(Stylist, '{"match_score": 55, "issues": []}')
    result = await stylist.review(
        draft="d", style_features={}, style_examples=[], style_guide="短句。"
    )
    # match_score < 70 → needs_revision True (derived when key absent)
    assert result["match_score"] == 55
    assert result["needs_revision"] is True


# ── Extractor ─────────────────────────────────────────────────────────────

async def test_extractor_default_on_garbage():
    extractor = make_agent(Extractor, "oops")
    result = await extractor.extract(
        final_content="c", outline="o", character_cards=[],
        world_settings={}, chapter_number=1,
    )
    assert result == DEFAULT_EXTRACTION


async def test_extractor_repairs_truncated_json():
    # The extraction response is a large multi-field JSON that the model often
    # truncates. With repair enabled, the fields emitted before the cut (here
    # chapter_summary) must be recovered rather than lost to the fallback.
    truncated = (
        '{"chapter_summary": "主角穿越廢墟前往波士頓。", '
        '"plot_milestones": [{"milestone": "A"}, {"milestone": "B"'
    )
    extractor = make_agent(Extractor, truncated)
    result = await extractor.extract(
        final_content="c", outline="o", character_cards=[],
        world_settings={}, chapter_number=1,
    )
    assert result["chapter_summary"] == "主角穿越廢墟前往波士頓。"
    assert result != DEFAULT_EXTRACTION


def test_extractor_prompt_puts_summary_first():
    # Guard the root-cause fix: the summary must be emitted first so a truncated
    # response can never lose it (previously it was field #6 and got cut off).
    from app.agents.extractor import SYSTEM_PROMPT as EXTRACTOR_PROMPT
    assert "第一個欄位就是 chapter_summary" in EXTRACTOR_PROMPT
    assert EXTRACTOR_PROMPT.index("chapter_summary") < EXTRACTOR_PROMPT.index("new_characters")


# ── Foreseer (truncated-JSON repair) ────────────────────────────────────────

async def test_foreseer_repairs_truncated_json():
    truncated = '{"overall_assessment": "還行", "branches": [{"title": "A"}, {"title": "B"'
    foreseer = make_agent(Foreseer, truncated)
    result = await foreseer.plan_next(
        final_content="c", chapter_number=1, outline="o",
        character_cards=[], world_settings={}, recent_hooks=[],
    )
    assert result["overall_assessment"] == "還行"
    assert len(result["branches"]) == 1
    assert result["branches"][0]["title"] == "A"


async def test_foreseer_includes_previous_summary():
    foreseer = make_agent(Foreseer, '{"branches": []}')
    await foreseer.plan_next(
        final_content="c", chapter_number=3, outline="o",
        character_cards=[], world_settings={}, recent_hooks=[],
        previous_chapters_summary="Chapter 1: 主角逃離廢墟。",
    )
    user_msg = foreseer.llm.calls[0]["messages"][1]["content"]
    assert "前文摘要" in user_msg
    assert "主角逃離廢墟" in user_msg


def test_foreseer_prompt_has_consistency_and_creativity():
    from app.agents.foreseer import SYSTEM_PROMPT as FORESEER_PROMPT
    assert "一致性原則" in FORESEER_PROMPT
    assert "創意原則" in FORESEER_PROMPT


async def test_foreseer_retries_on_empty_response():
    # First reply is blank (the failure mode that hid the suggestion block);
    # the agent should retry once and use the second, valid reply.
    foreseer = make_agent(Foreseer, ["", '{"branches": [{"title": "反轉"}]}'])
    result = await foreseer.plan_next(
        final_content="c", chapter_number=1, outline="o",
        character_cards=[], world_settings={}, recent_hooks=[],
    )
    assert len(foreseer.llm.calls) == 2
    assert result["branches"][0]["title"] == "反轉"


async def test_foreseer_bounds_huge_input():
    from app.agents.foreseer import (
        _MAX_CHAPTER_CHARS,
        _MAX_PREV_SUMMARY_CHARS,
    )

    huge_chapter = "字" * 10000
    huge_prev = "\n".join(f"Chapter {i}: {'摘' * 300}" for i in range(1, 40))
    foreseer = make_agent(Foreseer, '{"branches": []}')
    await foreseer.plan_next(
        final_content=huge_chapter,
        chapter_number=40,
        outline="o",
        character_cards=[],
        world_settings={},
        recent_hooks=[],
        previous_chapters_summary=huge_prev,
    )
    user_msg = foreseer.llm.calls[0]["messages"][1]["content"]
    # The full 10k-char chapter must NOT be embedded verbatim.
    assert "字" * (_MAX_CHAPTER_CHARS + 100) not in user_msg
    assert "…（前文省略）…" in user_msg
    assert "…（較早章節省略）…" in user_msg
    # The whole prompt stays comfortably small.
    assert len(user_msg) < _MAX_CHAPTER_CHARS + _MAX_PREV_SUMMARY_CHARS + 2000


def test_weaver_prompt_has_craft_block():
    from app.agents.weaver import SYSTEM_PROMPT as WEAVER_PROMPT
    assert "場景化" in WEAVER_PROMPT
    assert "Show, don't tell" in WEAVER_PROMPT
    assert "不要只是複述大綱" in WEAVER_PROMPT
    assert "務必寫到自然收尾" in WEAVER_PROMPT


def test_weaver_prompt_has_long_arc_block():
    from app.agents.weaver import SYSTEM_PROMPT as WEAVER_PROMPT
    assert "服務整體弧線" in WEAVER_PROMPT
    assert "不要提前解決主線" in WEAVER_PROMPT
    assert "推進而非原地踏步" in WEAVER_PROMPT


async def test_weaver_includes_milestones_progress():
    weaver = make_agent(Weaver, '{"content": "正文", "tokens_used": 5}')
    milestones = "## 已達成的情節里程碑（前面各章）\n- 第1章：主角逃離廢墟"
    await weaver.write(**_WEAVER_KWARGS, milestones_progress=milestones)
    user_msg = weaver.llm.calls[0]["messages"][1]["content"]
    assert "已達成的情節里程碑" in user_msg
    assert "主角逃離廢墟" in user_msg


def test_foreseer_prompt_has_long_arc_block():
    from app.agents.foreseer import SYSTEM_PROMPT as FORESEER_PROMPT
    assert "長篇弧線" in FORESEER_PROMPT
    assert "推動而非發散" in FORESEER_PROMPT
    assert "過早解決核心衝突" in FORESEER_PROMPT


async def test_foreseer_includes_milestones_progress():
    foreseer = make_agent(Foreseer, '{"branches": []}')
    milestones = "## 已達成的情節里程碑（前面各章）\n- 第2章：結識夥伴塔娜"
    await foreseer.plan_next(
        final_content="c", chapter_number=3, outline="o",
        character_cards=[], world_settings={}, recent_hooks=[],
        milestones_progress=milestones,
    )
    user_msg = foreseer.llm.calls[0]["messages"][1]["content"]
    assert "已達成的情節里程碑" in user_msg
    assert "結識夥伴塔娜" in user_msg


# ── Architect (arc plan generation & maintenance) ───────────────────────────

def test_normalize_plan_fills_missing_keys_and_milestone_ids():
    raw = {
        "theme": "復仇與救贖",
        "milestones": [{"title": "開端"}, "純字串里程碑"],
        "total_chapters": "12",
    }
    plan = _normalize_plan(raw)
    # Every expected key exists.
    for key in ("theme", "central_conflict", "total_chapters", "acts",
                "milestones", "character_arcs", "subplots", "updated_at_chapter"):
        assert key in plan
    # total_chapters coerced to int.
    assert plan["total_chapters"] == 12
    # Milestones get ids + a default status; plain strings are wrapped.
    assert plan["milestones"][0]["id"] == "m1"
    assert plan["milestones"][0]["status"] == "pending"
    assert plan["milestones"][1]["title"] == "純字串里程碑"


async def test_architect_generate_retries_on_empty_reply():
    valid = '{"theme": "t", "central_conflict": "c", "total_chapters": 10, "milestones": [{"title": "開端", "target_chapter": 1}]}'
    architect = make_agent(Architect, ["", valid])
    plan = await architect.generate(title="書名", outline="大綱")
    assert len(architect.llm.calls) == 2
    assert plan["theme"] == "t"
    assert plan["milestones"][0]["status"] == "pending"


async def test_architect_update_marks_milestone_achieved():
    current = _normalize_plan({
        "theme": "t",
        "milestones": [
            {"id": "m1", "title": "逃離廢墟", "target_chapter": 1, "status": "pending"},
            {"id": "m2", "title": "決戰", "target_chapter": 10, "status": "pending"},
        ],
    })
    updated_json = (
        '{"theme": "t", "milestones": ['
        '{"id": "m1", "title": "逃離廢墟", "target_chapter": 1, "status": "achieved", "achieved_chapter": 2},'
        '{"id": "m2", "title": "決戰", "target_chapter": 10, "status": "pending"}],'
        '"updated_at_chapter": 2}'
    )
    architect = make_agent(Architect, updated_json)
    plan = await architect.update(
        current_plan=current, chapter_number=2,
        chapter_summary="主角逃出了廢墟。", milestones_achieved=["逃離廢墟"],
    )
    assert plan["updated_at_chapter"] == 2
    m1 = next(m for m in plan["milestones"] if m["id"] == "m1")
    assert m1["status"] == "achieved"
    assert m1["achieved_chapter"] == 2


async def test_architect_update_keeps_plan_on_empty_reply():
    current = _normalize_plan({
        "theme": "t",
        "milestones": [{"id": "m1", "title": "開端", "target_chapter": 1, "status": "pending"}],
    })
    architect = make_agent(Architect, "")
    plan = await architect.update(current_plan=current, chapter_number=3, chapter_summary="s")
    # Empty reply → keep the existing plan, just bump the chapter marker.
    assert plan["updated_at_chapter"] == 3
    assert len(plan["milestones"]) == 1
    assert plan["milestones"][0]["title"] == "開端"


async def test_architect_update_keeps_plan_on_empty_plan_result():
    current = _normalize_plan({
        "theme": "t",
        "milestones": [{"id": "m1", "title": "開端", "target_chapter": 1, "status": "pending"}],
    })
    # Model returns a valid-but-empty plan; we must not wipe the real plan.
    architect = make_agent(Architect, '{"theme": "", "milestones": []}')
    plan = await architect.update(current_plan=current, chapter_number=4, chapter_summary="s")
    assert plan["updated_at_chapter"] == 4
    assert len(plan["milestones"]) == 1
    assert plan["milestones"][0]["title"] == "開端"


async def test_weaver_includes_arc_plan_summary():
    weaver = make_agent(Weaver, '{"content": "正文", "tokens_used": 5}')
    arc = "## 故事藍圖（整體弧線）\n核心衝突（切勿提前解決）：復仇"
    await weaver.write(**_WEAVER_KWARGS, arc_plan_summary=arc)
    user_msg = weaver.llm.calls[0]["messages"][1]["content"]
    assert "故事藍圖" in user_msg
    assert "切勿提前解決" in user_msg


async def test_foreseer_includes_arc_plan_summary():
    foreseer = make_agent(Foreseer, '{"branches": []}')
    arc = "## 故事藍圖（整體弧線）\n接下來待達成的里程碑：\n- [目標第5章] 中點反轉"
    await foreseer.plan_next(
        final_content="c", chapter_number=3, outline="o",
        character_cards=[], world_settings={}, recent_hooks=[],
        arc_plan_summary=arc,
    )
    user_msg = foreseer.llm.calls[0]["messages"][1]["content"]
    assert "故事藍圖" in user_msg
    assert "中點反轉" in user_msg


# ── EditorAnalyst (post-processing constraints) ─────────────────────────────

async def test_editor_analyst_enforces_rule_constraints():
    rules = [{"name": f"r{i}", "strength": (i % 5) + 1} for i in range(15)]
    rules.append({"name": "dead", "strength": 0})  # should be dropped
    rules.append({"name": "overcap", "strength": 9})  # should be capped to 5
    import json as _json
    editor = make_agent(EditorAnalyst, _json.dumps({"rules": rules, "summary": "s"}))
    result = await editor.learn(
        draft="d", final="f", existing_preferences=None, chapter_number=3,
    )
    assert len(result["rules"]) <= 12
    assert all(r["strength"] > 0 for r in result["rules"])
    assert all(r["strength"] <= 5 for r in result["rules"])
    assert result["last_chapter"] == 3
    assert result["chapters_analyzed"] == 1  # first-time analysis


# ── Profiler (default-structure fill incl. style_guide) ─────────────────────

async def test_profiler_fills_defaults_including_style_guide():
    # LLM returns only a partial profile; missing keys must be back-filled.
    profiler = make_agent(Profiler, '{"lexicon": {"vocabulary_level": "advanced"}}')
    result = await profiler.analyze(["some sample text"])
    # provided value preserved
    assert result["lexicon"]["vocabulary_level"] == "advanced"
    # missing subkeys back-filled
    assert "frequent_phrases" in result["lexicon"]
    # all top-level sections present, including the new content-free guide
    for key in ("lexicon", "syntax", "rhetoric", "narrative", "tone", "style_guide"):
        assert key in result
    assert result["style_guide"] == ""


async def test_profiler_merge_profiles_consolidates():
    merged = '{"lexicon": {"vocabulary_level": "literary"}, "style_guide": "短句為主。"}'
    profiler = make_agent(Profiler, merged)
    partials = [
        {"lexicon": {"vocabulary_level": "literary"}, "style_guide": "短句。"},
        {"lexicon": {"vocabulary_level": "advanced"}, "style_guide": "感官描寫。"},
    ]
    result = await profiler.merge_profiles(partials)
    # parsed values preserved
    assert result["lexicon"]["vocabulary_level"] == "literary"
    assert result["style_guide"] == "短句為主。"
    # missing sections back-filled with defaults
    assert result["syntax"]["avg_sentence_length"] == "medium"
    assert "tone" in result and "narrative" in result
    # the merge prompt received every partial profile
    sent = profiler.llm.calls[0]["messages"][1]["content"]
    assert "advanced" in sent and "literary" in sent
