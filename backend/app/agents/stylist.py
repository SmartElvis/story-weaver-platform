"""
Stylist Agent (風格校正師)
Reviews drafts for style consistency against the author's established style profile.
"""

import json

from app.agents.base import BaseAgent

SYSTEM_PROMPT = """你是一位精準的文學風格校正師（風格校正師）。你的任務是審查小說草稿，確保其與作者的既定寫作風格一致。

【最高原則｜內容隔離】
- 風格範例僅供你判斷「寫作技巧」的參照，嚴禁在你的輸出中引用、複述或提及參考作品裡的任何人物名稱、地名、專有名詞、情節或世界觀。
- issues 的 description、example、suggestion 都只能針對「待審查草稿」本身的寫作技巧（用詞、句式、修辭、節奏、視角、語氣）給出意見；example 只可摘錄草稿原文，絕不可摘錄參考範例的文字。

你將收到：
1. 草稿文本
2. 作者的風格特徵分析（包含詞彙、句法、修辭、敘事、語調五個維度）
3. 作者的風格範例文本
4. 寫作偏好（如有）

請從以下方面進行評估：
- 詞彙選擇是否符合作者的詞彙水平和習慣用語
- 句式結構是否符合作者的句法模式
- 修辭手法是否符合作者的修辭風格
- 敘事視角和節奏是否一致
- 整體語調和情感強度是否匹配

評分標準（match_score 0-100）：
- 90-100：完美匹配，幾乎無法區分
- 70-89：高度匹配，僅有細微差異
- 50-69：中等匹配，存在明顯風格偏離
- 30-49：低度匹配，大量不一致
- 0-29：嚴重不匹配

請以JSON格式回傳結果：
{
  "match_score": 0-100的整數,
  "issues": [
    {
      "type": "問題類型（vocabulary/syntax/rhetoric/narrative/tone）",
      "description": "具體描述哪裡不符合風格",
      "example": "原文中的問題片段",
      "suggestion": "建議修改方向"
    }
  ],
  "revised_content": "如果match_score < 70則提供修訂版本，否則為null",
  "needs_revision": true/false
}

判斷 needs_revision 的標準：
- match_score < 70 → true
- match_score >= 70 → false"""


# Safe default returned when the LLM response cannot be parsed as JSON.
DEFAULT_STYLE_REVIEW = {
    "match_score": 75,
    "issues": [],
    "revised_content": None,
    "needs_revision": False,
}


class Stylist(BaseAgent):
    """Reviews drafts for style consistency against the author's profile."""

    agent_name = "stylist"

    async def review(
        self,
        draft: str,
        style_features: dict,
        style_examples: list[str],
        style_guide: str = "",
        writing_preferences: str = "",
    ) -> dict:
        """
        Review a draft for style consistency.

        Args:
            draft: The chapter draft text to review.
            style_features: Style profile dict from Profiler.
            style_examples: Example text snippets showing desired style.
            style_guide: Content-free natural-language style guide (technique only).
            writing_preferences: Editor-learned writing preferences.

        Returns:
            dict with keys: match_score, issues, revised_content, needs_revision
        """
        sections = []

        sections.append(f"## 待審查草稿\n{draft}")

        if style_features:
            sections.append(
                f"## 作者風格特徵\n{json.dumps(style_features, ensure_ascii=False, indent=2)}"
            )

        if style_guide:
            sections.append(f"## 風格指南\n{style_guide}")

        if style_examples:
            examples_text = "\n---\n".join(style_examples[:3])
            sections.append(f"## 作者風格範例\n{examples_text}")

        if writing_preferences:
            sections.append(f"## 寫作偏好\n{writing_preferences}")

        user_message = "\n\n".join(sections)
        user_message += "\n\n請對以上草稿進行風格一致性審查，以JSON格式回傳結果。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=2500,
        )

        result = self._parse_json_response(raw_response, fallback=DEFAULT_STYLE_REVIEW)

        # Ensure required keys with defaults
        if "match_score" not in result:
            result["match_score"] = 75
        if "issues" not in result:
            result["issues"] = []
        if "revised_content" not in result:
            result["revised_content"] = None
        if "needs_revision" not in result:
            result["needs_revision"] = result["match_score"] < 70

        return result
