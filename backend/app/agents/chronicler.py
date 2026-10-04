"""
Chronicler Agent (邏輯守護者)
Reviews drafts for logical consistency, plot holes, character behavior,
timeline errors, and world rule violations.
"""

import json

from app.agents.base import BaseAgent

SYSTEM_PROMPT = """你是一位嚴謹的小說邏輯審稿師（邏輯守護者）。你的任務是審查小說草稿，找出所有邏輯問題和不一致之處。

請從以下五個維度進行檢查：

1. **情節漏洞（plot_holes）**：劇情中不合邏輯或未解釋的事件
2. **角色一致性（character_consistency）**：角色的言行是否符合其設定
3. **時間線（timeline）**：事件發生的時間順序是否合理
4. **世界規則（world_rules）**：是否違反了已建立的世界觀設定
5. **連續性（continuity）**：與前文是否有矛盾或斷層

對每個發現的問題，請標注嚴重程度：
- low：小瑕疵，不影響閱讀體驗
- medium：明顯問題，可能困擾讀者
- high：嚴重錯誤，破壞故事可信度

請以JSON格式回傳結果：
{
  "issues": [
    {
      "category": "問題類別",
      "description": "問題描述",
      "location": "問題所在段落或位置描述",
      "severity": "low/medium/high"
    }
  ],
  "severity": "整體嚴重程度（取最高值）",
  "suggestions": ["修改建議1", "修改建議2"],
  "needs_revision": true/false
}

判斷 needs_revision 的標準：
- 存在任何 high 級別問題 → true
- 存在2個以上 medium 級別問題 → true
- 僅有 low 級別問題 → false"""


# Safe default returned when the LLM response cannot be parsed as JSON.
DEFAULT_REVIEW = {
    "issues": [],
    "severity": "low",
    "suggestions": ["Unable to parse review result; manual review recommended."],
    "needs_revision": False,
}


class Chronicler(BaseAgent):
    """Reviews drafts for logical consistency and continuity."""

    agent_name = "chronicler"

    async def review(
        self,
        draft: str,
        outline: str,
        character_cards: list[dict],
        world_settings: dict,
        previous_chapters_summary: str,
        chapter_number: int,
    ) -> dict:
        """
        Review a draft for logical issues.

        Args:
            draft: The chapter draft text to review.
            outline: The story outline.
            character_cards: List of character card dicts.
            world_settings: World-building settings dict.
            previous_chapters_summary: Summary of previous chapters.
            chapter_number: Current chapter number.

        Returns:
            dict with keys: issues, severity, suggestions, needs_revision
        """
        sections = []

        sections.append(f"## 審查對象\n第 {chapter_number} 章草稿：\n\n{draft}")

        if outline:
            sections.append(f"## 故事大綱\n{outline}")

        if previous_chapters_summary:
            sections.append(f"## 前文摘要\n{previous_chapters_summary}")

        if character_cards:
            cards_text = "\n".join(
                f"- **{c.get('name', '未命名')}**: {json.dumps(c, ensure_ascii=False)}"
                for c in character_cards
            )
            sections.append(f"## 角色卡\n{cards_text}")

        if world_settings:
            sections.append(
                f"## 世界設定\n{json.dumps(world_settings, ensure_ascii=False, indent=2)}"
            )

        user_message = "\n\n".join(sections)
        user_message += "\n\n請對以上草稿進行邏輯審查，以JSON格式回傳結果。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=2500,
        )

        result = self._parse_json_response(raw_response, fallback=DEFAULT_REVIEW)

        # Ensure required keys with defaults
        if "issues" not in result:
            result["issues"] = []
        if "severity" not in result:
            # Derive from issues
            severities = [i.get("severity", "low") for i in result["issues"]]
            if "high" in severities:
                result["severity"] = "high"
            elif "medium" in severities:
                result["severity"] = "medium"
            else:
                result["severity"] = "low"
        if "suggestions" not in result:
            result["suggestions"] = []
        if "needs_revision" not in result:
            high_count = sum(
                1 for i in result["issues"] if i.get("severity") == "high"
            )
            medium_count = sum(
                1 for i in result["issues"] if i.get("severity") == "medium"
            )
            result["needs_revision"] = high_count > 0 or medium_count > 2

        return result
