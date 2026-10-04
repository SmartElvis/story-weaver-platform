"""
Architect Agent (建築師)
Designs and maintains the structured "故事藍圖" (arc plan) for a project: a
three-act structure, plot milestones with target chapters, character arcs, and
subplots.

The arc plan is the macro-structure that keeps a long novel coherent. It is
generated once from the outline (on demand) and then refreshed after each
chapter is finalized, so milestone status and the trajectory stay current.
Generation agents (Weaver, Foreseer) receive a compact rendering of it so every
chapter knows where it sits in the whole story.

arc_plan shape::

    {
      "theme": str,                 # 核心主題
      "central_conflict": str,      # 貫穿全書的核心衝突
      "total_chapters": int,        # 預估總章數
      "acts": [{"name", "chapter_range", "goal"}],
      "milestones": [{"id", "title", "description", "target_chapter",
                       "act", "status", "achieved_chapter"}],
      "character_arcs": [{"name", "want", "need", "transformation"}],
      "subplots": [{"name", "summary", "status"}],
      "updated_at_chapter": int,    # 最後更新到第幾章
    }
"""

from __future__ import annotations

import json
import logging

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

GENERATE_PROMPT = """你是一位資深的故事架構師（建築師）。你的任務是根據提供的故事素材，為一部**中長篇小說**設計一份結構化的「故事藍圖」（arc plan），作為後續每一章創作的總綱。

設計原則：
- **三幕結構**（或起承轉合）：把全書劃分為幾個階段，每個階段有明確的章節區間與敘事目標。
- **里程碑驅動**：把故事拆成若干關鍵里程碑（開端事件、中點反轉、高潮、結局等），每個里程碑指定一個**目標章節**，讓推進有方向感。
- **角色弧線**：為主要角色設計 want（表面慾望）與 need（真正需要）以及轉變方向。
- **核心衝突**要能貫穿全書，**不要在前期里程碑就解決它**——高潮留到後段。
- 藍圖要承接提供的故事大綱，不要憑空另起爐灶；素材不足處做合理補足。

請以JSON格式回傳以下結構（不要使用程式碼區塊）：

{
  "theme": "核心主題（1-2句話）",
  "central_conflict": "貫穿全書的核心衝突（1-2句話）",
  "total_chapters": 20,
  "acts": [
    {"name": "第一幕：鋪陳", "chapter_range": "1-5", "goal": "這一幕要達成的敘事目標"}
  ],
  "milestones": [
    {"id": "m1", "title": "里程碑標題", "description": "簡述這個里程碑的事件與意義", "target_chapter": 3, "act": 1, "status": "pending"}
  ],
  "character_arcs": [
    {"name": "角色名", "want": "表面慾望", "need": "真正需要", "transformation": "轉變方向"}
  ],
  "subplots": [
    {"name": "支線名", "summary": "支線摘要", "status": "pending"}
  ]
}

要求：
- acts 通常 3-4 個，chapter_range 用字串表示（如 "1-5"），相鄰區間應銜接。
- milestones 至少 5 個，按 target_chapter 由小到大排列，id 用 m1、m2… 遞增。
- 所有 milestone 的 status 初始 đều是 "pending"。
- total_chapters 應大於等於最後一個里程碑的 target_chapter。"""


UPDATE_PROMPT = """你是一位資深的故事架構師（建築師）。以下是這部小說目前的「故事藍圖」（arc plan），以及剛完成章節的最新進展。請根據新進展**更新這份藍圖**，然後回傳**完整的更新後藍圖**（同樣的JSON結構）。

更新規則：
- 對照剛完成章節達成的里程碑，把對應 milestone 的 status 改為 "achieved"，並填上 achieved_chapter（達成於第幾章）。若里程碑標題不完全相同但語義相符，也應視為達成。
- 可根據實際劇情走向，**微調**尚未達成里程碑的 target_chapter 或描述，使藍圖更貼合真實發展；但不要大幅推翻整體結構。
- 若劇情衍生出新的支線或角色弧線，可補充；已解決的支線可把 status 改為 "resolved"。
- 把 updated_at_chapter 設為剛完成的章節號。
- 保持 theme、central_conflict、acts 大致穩定（除非劇情有重大轉折）。

請回傳**完整**的更新後 JSON 藍圖（包含所有欄位與全部里程碑，不要省略），不要使用程式碼區塊。"""


# Safe default returned when the LLM response cannot be parsed even after repair.
DEFAULT_ARC_PLAN = {
    "theme": "",
    "central_conflict": "",
    "total_chapters": 0,
    "acts": [],
    "milestones": [],
    "character_arcs": [],
    "subplots": [],
    "updated_at_chapter": 0,
}


def _normalize_plan(plan: dict) -> dict:
    """Ensure an arc plan has every expected key with a sane type.

    Fills missing keys from ``DEFAULT_ARC_PLAN`` and guarantees each milestone
    carries an ``id`` and a ``status`` so downstream rendering and status
    tracking never crash on partial model output.
    """
    if not isinstance(plan, dict):
        plan = {}
    result = dict(DEFAULT_ARC_PLAN)
    result.update({k: v for k, v in plan.items() if v is not None})

    for key in ("acts", "milestones", "character_arcs", "subplots"):
        if not isinstance(result.get(key), list):
            result[key] = []

    if not isinstance(result.get("total_chapters"), int):
        try:
            result["total_chapters"] = int(result.get("total_chapters") or 0)
        except (TypeError, ValueError):
            result["total_chapters"] = 0
    if not isinstance(result.get("updated_at_chapter"), int):
        try:
            result["updated_at_chapter"] = int(result.get("updated_at_chapter") or 0)
        except (TypeError, ValueError):
            result["updated_at_chapter"] = 0

    # Guarantee milestone ids + status so rendering/tracking is safe.
    for idx, milestone in enumerate(result["milestones"]):
        if not isinstance(milestone, dict):
            result["milestones"][idx] = {"id": f"m{idx + 1}", "title": str(milestone), "status": "pending"}
            continue
        milestone.setdefault("id", f"m{idx + 1}")
        milestone.setdefault("title", "")
        milestone.setdefault("status", "pending")
        milestone.setdefault("achieved_chapter", None)

    return result


class Architect(BaseAgent):
    """Designs and maintains the structured arc plan for a project."""

    agent_name = "architect"

    async def generate(
        self,
        title: str,
        outline: str,
        genre: str = "",
        character_cards: list[dict] | None = None,
        world_settings: dict | None = None,
        total_chapters_hint: int | None = None,
    ) -> dict:
        """Generate a fresh arc plan from the project's source material."""
        sections = [f"## 作品標題\n{title}"]
        if genre:
            sections.append(f"## 類型\n{genre}")
        if outline:
            sections.append(f"## 故事大綱\n{outline}")
        if character_cards:
            cards_text = "\n".join(
                f"- **{c.get('name', '未命名')}**: {c.get('description', '')}"
                for c in character_cards
            )
            sections.append(f"## 主要角色\n{cards_text}")
        if world_settings:
            sections.append(
                f"## 世界設定\n{json.dumps(world_settings, ensure_ascii=False)}"
            )
        if total_chapters_hint:
            sections.append(f"## 預估章數參考\n約 {total_chapters_hint} 章")

        user_message = "\n\n".join(sections)
        user_message += "\n\n請根據以上素材，設計這份故事藍圖，以JSON格式回傳。"

        messages = [
            {"role": "system", "content": GENERATE_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages, temperature=0.7, max_tokens=5000
        )
        if not raw_response or not raw_response.strip():
            logger.warning("Architect.generate received an empty LLM reply; retrying once")
            raw_response = await self.llm.chat(
                messages=messages, temperature=0.8, max_tokens=5000
            )

        plan = self._parse_json_response(
            raw_response, fallback=DEFAULT_ARC_PLAN, repair_truncated=True
        )
        return _normalize_plan(plan)

    async def update(
        self,
        current_plan: dict,
        chapter_number: int,
        chapter_summary: str,
        milestones_achieved: list[str] | None = None,
        open_hooks: list[str] | None = None,
    ) -> dict:
        """Refresh the arc plan after a chapter is finalized.

        Falls back to the existing plan (with ``updated_at_chapter`` bumped) if
        the model response cannot be parsed, so a bad update never destroys a
        good plan.
        """
        base = _normalize_plan(current_plan or {})

        sections = [
            f"## 目前的故事藍圖\n{json.dumps(base, ensure_ascii=False, indent=2)}",
            f"## 剛完成的第 {chapter_number} 章摘要\n{chapter_summary or '（無摘要）'}",
        ]
        if milestones_achieved:
            sections.append(
                "## 本章達成的里程碑\n"
                + "\n".join(f"- {m}" for m in milestones_achieved)
            )
        if open_hooks:
            sections.append(
                "## 本章新增/仍開放的伏筆\n"
                + "\n".join(f"- {h}" for h in open_hooks)
            )

        user_message = "\n\n".join(sections)
        user_message += f"\n\n第 {chapter_number} 章已完成，請回傳更新後的完整藍圖JSON。"

        messages = [
            {"role": "system", "content": UPDATE_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages, temperature=0.5, max_tokens=5000
        )
        if not raw_response or not raw_response.strip():
            logger.warning("Architect.update received an empty LLM reply; keeping current plan")
            base["updated_at_chapter"] = chapter_number
            return base

        try:
            parsed = self._parse_json_response(
                raw_response, fallback=DEFAULT_ARC_PLAN, repair_truncated=True
            )
        except Exception:  # noqa: BLE001 - never let an update destroy the plan
            parsed = DEFAULT_ARC_PLAN

        normalized = _normalize_plan(parsed)
        # If parsing collapsed to an empty plan, keep the existing one instead.
        if not normalized.get("milestones") and base.get("milestones"):
            logger.warning("Architect.update produced an empty plan; keeping current plan")
            base["updated_at_chapter"] = chapter_number
            return base

        normalized["updated_at_chapter"] = chapter_number
        return normalized
