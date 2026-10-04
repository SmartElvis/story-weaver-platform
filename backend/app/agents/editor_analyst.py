"""
Editor Analyst Agent (編輯分析師)
Learns from user edits by comparing draft vs final content,
building a cumulative preference profile that improves future generation.
"""

import json
from typing import Optional

from app.agents.base import BaseAgent

SYSTEM_PROMPT = """你是一位敏銳的編輯分析師（編輯分析師）。你的任務是通過比較草稿和定稿之間的差異，學習用戶的寫作偏好和編輯模式。

你將收到：
1. 原始草稿
2. 用戶編輯後的定稿
3. 差異摘要（diff_info）
4. 現有的偏好規則（如有）
5. 當前章節編號

你的目標是維護一個偏好規則集（最多12條規則），格式如下：
{
  "rules": [
    {
      "category": "規則類別（vocabulary/syntax/rhetoric/narrative/tone/structure/pacing）",
      "directive": "具體的寫作指令（例如：'避免使用過長的從句'、'對話後總是接動作描寫'）",
      "strength": 1-5的整數（出現次數/重要程度）,
      "example": "從文本中提取的具體範例"
    }
  ],
  "summary": "偏好總結（一段話概括主要寫作偏好）",
  "chapters_analyzed": 已分析的章節數,
  "last_chapter": 最後分析的章節編號
}

規則管理邏輯：
- 如果某個編輯模式在之前的規則中已存在（相似含義），則 strength + 1（最高5）
- 全新的編輯模式，新建規則，strength 從 1 開始
- 如果定稿中反而使用了之前規則禁止的模式（矛盾），則該規則 strength - 1
- strength 降到 0 的規則應被移除
- 總規則數量不超過 12 條，如果超出，移除 strength 最低的規則

請仔細分析差異，只提取有意義的、可重複的寫作偏好模式，忽略一次性的內容修改。
以JSON格式回傳更新後的完整偏好profile。"""


class EditorAnalyst(BaseAgent):
    """Learns writing preferences from user edits to improve future generation."""

    agent_name = "editor_analyst"

    async def learn(
        self,
        draft: str,
        final: str,
        existing_preferences: Optional[dict],
        chapter_number: int,
        diff_info: str = "",
    ) -> dict:
        """
        Learn from user edits by comparing draft vs final content.

        Args:
            draft: The original AI-generated draft.
            final: The user-edited final content.
            existing_preferences: Current preference profile dict (or None if first time).
            chapter_number: Current chapter number.
            diff_info: A summary of the differences between draft and final.

        Returns:
            Updated preference profile dict with keys:
            rules, summary, chapters_analyzed, last_chapter
        """
        sections = []

        sections.append(f"## 原始草稿\n{draft}")
        sections.append(f"## 用戶編輯後的定稿\n{final}")

        if diff_info:
            sections.append(f"## 差異摘要\n{diff_info}")

        if existing_preferences:
            sections.append(
                f"## 現有偏好規則\n{json.dumps(existing_preferences, ensure_ascii=False, indent=2)}"
            )
        else:
            sections.append("## 現有偏好規則\n（這是第一次分析，尚無既有規則）")

        sections.append(f"## 當前章節編號\n第 {chapter_number} 章")

        user_message = "\n\n".join(sections)
        user_message += "\n\n請分析用戶的編輯模式，更新偏好profile，以JSON格式回傳。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=2500,
        )

        result = self._parse_json_response(raw_response)

        # Ensure required keys
        if "rules" not in result:
            result["rules"] = existing_preferences.get("rules", []) if existing_preferences else []
        if "summary" not in result:
            result["summary"] = ""
        if "chapters_analyzed" not in result:
            prev_count = existing_preferences.get("chapters_analyzed", 0) if existing_preferences else 0
            result["chapters_analyzed"] = prev_count + 1
        if "last_chapter" not in result:
            result["last_chapter"] = chapter_number

        # Enforce rules constraints
        # Remove rules with strength <= 0
        result["rules"] = [r for r in result["rules"] if r.get("strength", 0) > 0]
        # Cap strength at 5
        for rule in result["rules"]:
            rule["strength"] = min(rule.get("strength", 1), 5)
        # Limit to 12 rules, keep highest strength
        if len(result["rules"]) > 12:
            result["rules"] = sorted(
                result["rules"], key=lambda r: r.get("strength", 0), reverse=True
            )[:12]

        return result

    @classmethod
    def format_for_prompt(cls, preferences: Optional[dict], min_strength: int = 2) -> str:
        """
        Format preference rules for injection into the Weaver prompt.

        Args:
            preferences: The preference profile dict.
            min_strength: Minimum strength threshold for including a rule.

        Returns:
            Formatted string of writing preferences for prompt injection.
        """
        if not preferences or not preferences.get("rules"):
            return ""

        filtered_rules = [
            r for r in preferences["rules"]
            if r.get("strength", 0) >= min_strength
        ]

        if not filtered_rules:
            return ""

        lines = ["以下是根據用戶過去的編輯行為學習到的寫作偏好，請在寫作時遵守：", ""]

        # Sort by strength descending
        sorted_rules = sorted(
            filtered_rules, key=lambda r: r.get("strength", 0), reverse=True
        )

        for i, rule in enumerate(sorted_rules, 1):
            strength_indicator = "*" * rule.get("strength", 1)
            category = rule.get("category", "general")
            directive = rule.get("directive", "")
            example = rule.get("example", "")

            line = f"{i}. [{category}] {directive} ({strength_indicator})"
            if example:
                line += f"\n   範例：{example}"
            lines.append(line)

        if preferences.get("summary"):
            lines.append("")
            lines.append(f"總結：{preferences['summary']}")

        return "\n".join(lines)
