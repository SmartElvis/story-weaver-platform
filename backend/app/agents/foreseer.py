"""
Foreseer Agent (策劃者)
Plans potential next chapter directions based on the current story state,
providing branching options with tension analysis and foreshadowing callbacks.
"""

import json
import logging

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位富有創意的故事策劃者（策劃者）。你的任務是在每章完成後，為下一章提供多種可能的發展方向。

你需要考慮：
- 故事的整體大綱和方向
- 當前劇情的發展勢頭
- 已埋設的伏筆和懸念
- 角色弧線的發展需求
- 情節的張力和節奏變化

【一致性原則（最高優先）】
- 你提出的任何方向都**必須**嚴格遵守已建立的世界觀規則、角色當前狀態與既成事實。
- **嚴禁**與前文矛盾：不得讓已死亡的角色復活、不得推翻已經發生的關鍵事件、不得違反已確立的世界規則。
- 若要引入新角色或新設定，必須能與現有劇情合理銜接，並說明其出現的邏輯。
- 優先參考「未解決的伏筆和懸念」與前文摘要，確保方向承接既有脈絡，而非憑空另起爐灶。

【創意原則】
- 在符合一致性的前提下，方向要**大膽、出人意料但合乎邏輯**，避免平淡的流水帳式延續。
- 每個方向都應帶有真正的**戲劇衝突與賭注（stakes）**：角色會失去什麼、面臨什麼兩難？
- 可考慮反轉、道德兩難、伏筆的意外回收、角色關係的質變等更有張力的設計。
- 三個方向之間要有**實質差異**（不同的核心衝突或價值選擇），而非同一情節的微調版本。

【長篇弧線｜推動而非發散】
- 你規劃的是一部**中長篇小說**的下一步，不是獨立故事。每個方向都應把整體故事**朝「故事大綱」的下一個階段推進**，而非天馬行空地另起爐灶。
- 參考「已達成的情節里程碑」，讓方向承接尚未完成的弧線：可分別對接**不同的里程碑、支線或角色弧線**，使三條路線各有推進重點。
- **嚴禁任何方向過早解決核心衝突**或讓主角輕易達成終極目標——高潮要留到全書後段。
- 方向必須讓故事**前進**（處境改變、賭注升高、關係質變），避免原地打轉或重複上一章已經寫過的情節。

請以JSON格式回傳以下結構：

{
  "overall_assessment": "對當前故事狀態的整體評估（2-3句話，包含節奏分析和發展建議）",
  "branches": [
    {
      "title": "方向標題（簡短有力）",
      "summary": "方向摘要（100-150字，描述這條路線的主要事件和發展）",
      "tension": "張力分析（rising/climax/falling/steady）",
      "new_characters": ["如果此方向需要引入新角色，列出名稱和簡述（字串格式）"],
      "suggested_direction": "給寫作者的具體寫作指令（150-200字，包含開場、核心事件、結尾方向）"
    }
  ],
  "foreshadowing_callbacks": [
    {
      "hook": "可以在下一章回收的伏筆",
      "callback_suggestion": "建議如何回收這個伏筆",
      "urgency": "回收的緊迫程度（high/medium/low）"
    }
  ]
}

要求：
- 提供2-3個不同的發展方向（branches），確保方向之間有明顯差異
- 每個方向要有不同的張力曲線
- 伏筆回收建議要結合現有的未解決伏筆
- 建議要具體可執行，不要過於抽象"""


# Safe default returned when the LLM response cannot be parsed even after repair.
DEFAULT_PLAN = {
    "overall_assessment": "Unable to parse planning result. Manual review recommended.",
    "branches": [],
    "foreshadowing_callbacks": [],
}


# ── Prompt-size bounds ──────────────────────────────────────────────────────
# The planning prompt must stay well within the model context window. When it
# overflows (full chapter text + every prior summary + a full world-settings
# dump), the provider tends to return an *empty* reply, which then parses to
# DEFAULT_PLAN with no branches — and the UI hides the whole suggestion block.
# Each section is therefore capped, keeping the parts that matter most for
# "what happens next" (the ending of the current chapter, the most recent
# chapters, the latest world rules).
_MAX_CHAPTER_CHARS = 3000       # keep the ending of the just-finished chapter
_MAX_PREV_SUMMARY_CHARS = 2500  # most recent chapters win
_MAX_WORLD_CHARS = 1500
_MAX_CARD_DESC_CHARS = 200


def _tail(text: str, limit: int) -> str:
    """Keep the END of ``text`` (the part most relevant to continuity)."""
    text = text or ""
    if len(text) <= limit:
        return text
    return "…（前文省略）…" + text[-limit:]


def _tail_lines(text: str, limit: int) -> str:
    """Keep the most recent newline-delimited entries within ``limit`` chars."""
    text = text or ""
    if len(text) <= limit:
        return text
    kept: list[str] = []
    total = 0
    for line in reversed(text.split("\n")):
        if total + len(line) + 1 > limit:
            break
        kept.append(line)
        total += len(line) + 1
    return "…（較早章節省略）…\n" + "\n".join(reversed(kept))


def _truncate(text: str, limit: int) -> str:
    """Keep the START of ``text`` and append an ellipsis if it is too long."""
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


class Foreseer(BaseAgent):
    """Plans potential next chapter directions based on current story state."""

    agent_name = "foreseer"

    async def plan_next(
        self,
        final_content: str,
        chapter_number: int,
        outline: str,
        character_cards: list[dict],
        world_settings: dict,
        recent_hooks: list[dict],
        previous_chapters_summary: str = "",
        milestones_progress: str = "",
        arc_plan_summary: str = "",
    ) -> dict:
        """
        Plan potential next chapter directions.

        Args:
            final_content: The finalized content of the current chapter.
            chapter_number: Current chapter number.
            outline: The story outline.
            character_cards: List of character card dicts.
            world_settings: World-building settings dict.
            recent_hooks: List of recent unresolved plot hooks.
            previous_chapters_summary: Summary of all earlier chapters, giving the
                broader arc so suggestions stay consistent with the whole story.
            milestones_progress: Formatted "已達成里程碑" block (from
                arc_context.format_milestones_progress) so branches push toward
                milestones not yet achieved instead of diverging randomly.
            arc_plan_summary: Formatted "故事藍圖" block (from
                arc_context.format_arc_plan) so branches align with the planned
                three-act structure and the next milestones.

        Returns:
            dict with keys: overall_assessment, branches, foreshadowing_callbacks
        """
        sections = []

        # Keep only the ending of the just-finished chapter — it matters most
        # for planning what comes next, and the full text would blow up the
        # prompt for long chapters.
        sections.append(
            f"## 剛完成的第 {chapter_number} 章\n"
            f"{_tail(final_content, _MAX_CHAPTER_CHARS)}"
        )

        if previous_chapters_summary:
            sections.append(
                f"## 前文摘要（之前各章）\n"
                f"{_tail_lines(previous_chapters_summary, _MAX_PREV_SUMMARY_CHARS)}"
            )

        if milestones_progress:
            sections.append(milestones_progress)

        if outline:
            sections.append(f"## 故事大綱\n{outline}")

        if arc_plan_summary:
            sections.append(arc_plan_summary)

        if character_cards:
            cards_text = "\n".join(
                f"- **{c.get('name', '未命名')}**: "
                f"{_truncate(c.get('description', ''), _MAX_CARD_DESC_CHARS)}"
                for c in character_cards
            )
            sections.append(f"## 主要角色\n{cards_text}")

        if world_settings:
            world_text = json.dumps(world_settings, ensure_ascii=False, indent=2)
            sections.append(
                f"## 世界設定\n{_tail(world_text, _MAX_WORLD_CHARS)}"
            )

        if recent_hooks:
            hooks_text = "\n".join(
                f"- {h.get('hook', '')}"
                + (f" (緊迫度: {h.get('urgency', 'medium')})" if "urgency" in h else "")
                for h in recent_hooks
            )
            sections.append(f"## 未解決的伏筆和懸念\n{hooks_text}")

        user_message = "\n\n".join(sections)
        user_message += f"\n\n第 {chapter_number} 章已完成，請為第 {chapter_number + 1} 章規劃2-3個可能的發展方向，以JSON格式回傳。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=4500,
        )

        # An empty reply usually means a transient provider hiccup (often tied
        # to an oversized prompt). Retry once before falling back to DEFAULT_PLAN,
        # so a single blank response doesn't silently hide the suggestion block.
        if not raw_response or not raw_response.strip():
            logger.warning("Foreseer received an empty LLM reply; retrying once")
            raw_response = await self.llm.chat(
                messages=messages,
                temperature=0.8,
                max_tokens=4500,
            )

        result = self._parse_json_response(
            raw_response, fallback=DEFAULT_PLAN, repair_truncated=True
        )

        # Ensure required keys exist
        if "overall_assessment" not in result:
            result["overall_assessment"] = ""
        if "branches" not in result:
            result["branches"] = []
        if "foreshadowing_callbacks" not in result:
            result["foreshadowing_callbacks"] = []

        # Validate branches structure
        for branch in result["branches"]:
            branch.setdefault("title", "Untitled")
            branch.setdefault("summary", "")
            branch.setdefault("tension", "steady")
            branch.setdefault("new_characters", [])
            branch.setdefault("suggested_direction", "")

        return result
