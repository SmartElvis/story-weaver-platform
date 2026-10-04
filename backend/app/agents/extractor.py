"""
Extractor Agent (情報提取官)
Extracts structured information from finalized chapter content, including
new characters, locations, world rules, plot hooks, and chapter summaries.
"""

import json

from app.agents.base import BaseAgent

SYSTEM_PROMPT = """你是一位精確的情報提取官（情報提取官）。你的任務是從定稿的小說章節中提取所有重要的結構化資訊，用於更新故事資料庫。

【最高原則｜摘要優先、整體精簡】
- 你必須以 JSON 輸出，且 **第一個欄位就是 chapter_summary**，務必先完整寫出它，再輸出其他欄位。即使後續內容因長度被截斷，也要確保 chapter_summary 已完整輸出。
- 所有欄位都要**精簡**：描述與說明控制在必要範圍內，避免冗長。
- **world_rules 的 source 欄位只需極短的出處提示（數個詞即可），嚴禁整句引用原文。**
- new_locations / new_characters 的 description 精簡扼要，不要長篇引用原文。

請提取以下資訊（請依此順序輸出 JSON）：

1. **chapter_summary**：本章劇情摘要（200-300字，包含主要事件、角色互動、情感轉折）。**務必第一個輸出。**

2. **new_characters**：本章新出場的角色
   - name: 角色名稱
   - description: 外貌和性格簡述（精簡）
   - role: 在故事中的角色定位（protagonist/antagonist/supporting/minor）
   - first_appearance_context: 首次出場的場景描述（精簡）

3. **updated_characters**：已有角色的重要變化
   - name: 角色名稱
   - changes: 發生了什麼變化（性格發展、狀態變化、關係變化等）
   - significance: 變化的重要性說明

4. **new_locations**：本章出現的新地點
   - name: 地點名稱
   - description: 地點描述（精簡）
   - significance: 對劇情的意義

5. **world_rules**：本章揭示或建立的世界觀規則
   - rule: 規則描述（精簡）
   - source: 極短的出處提示（數個詞，勿整句引用）
   - category: 規則類別（magic/social/physical/political/other）

6. **open_hooks**：未解決的伏筆或懸念
   - hook: 伏筆描述
   - setup_context: 伏筆設置的上下文（精簡）
   - potential_payoff: 可能的回收方式

7. **plot_milestones**：本章達成的情節里程碑
   - milestone: 里程碑描述
   - impact: 對整體劇情的影響

請以JSON格式回傳結果，確保所有資訊準確且來自文本本身，不要推測或添加文本中沒有的內容。再次提醒：chapter_summary 必須是 JSON 的第一個欄位。"""


# Safe default returned when the LLM response cannot be parsed as JSON.
DEFAULT_EXTRACTION = {
    "new_characters": [],
    "updated_characters": [],
    "new_locations": [],
    "world_rules": [],
    "open_hooks": [],
    "chapter_summary": "（本章摘要生成失敗，無法自動提取）",
    "plot_milestones": [],
}


class Extractor(BaseAgent):
    """Extracts structured information from finalized chapter content."""

    agent_name = "extractor"

    async def extract(
        self,
        final_content: str,
        outline: str,
        character_cards: list[dict],
        world_settings: dict,
        chapter_number: int,
    ) -> dict:
        """
        Extract structured information from finalized chapter content.

        Args:
            final_content: The finalized chapter text.
            outline: The story outline.
            character_cards: Existing character card dicts.
            world_settings: Existing world-building settings.
            chapter_number: Current chapter number.

        Returns:
            dict with keys: new_characters, updated_characters, new_locations,
                           world_rules, open_hooks, chapter_summary, plot_milestones
        """
        sections = []

        sections.append(f"## 第 {chapter_number} 章定稿內容\n{final_content}")

        if outline:
            sections.append(f"## 故事大綱\n{outline}")

        if character_cards:
            existing_names = [c.get("name", "未命名") for c in character_cards]
            cards_text = "\n".join(
                f"- **{c.get('name', '未命名')}**: {json.dumps(c, ensure_ascii=False)}"
                for c in character_cards
            )
            sections.append(
                f"## 已有角色（用於區分新舊角色）\n已知角色名稱：{', '.join(existing_names)}\n\n{cards_text}"
            )

        if world_settings:
            sections.append(
                f"## 已建立的世界設定\n{json.dumps(world_settings, ensure_ascii=False, indent=2)}"
            )

        user_message = "\n\n".join(sections)
        user_message += "\n\n請從以上定稿內容中提取所有重要資訊，以JSON格式回傳。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=6000,
        )

        result = self._parse_json_response(
            raw_response, fallback=DEFAULT_EXTRACTION, repair_truncated=True
        )

        # Ensure all required keys exist with defaults
        defaults = {
            "new_characters": [],
            "updated_characters": [],
            "new_locations": [],
            "world_rules": [],
            "open_hooks": [],
            "chapter_summary": "",
            "plot_milestones": [],
        }
        for key, default_val in defaults.items():
            if key not in result:
                result[key] = default_val

        return result
