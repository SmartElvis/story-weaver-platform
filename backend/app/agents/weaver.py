"""
Weaver Agent (情節編織者)
Generates chapter drafts based on direction, style, plot context, and world information.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位專業的小說寫作者（情節編織者）。你的任務是根據提供的指令和上下文，撰寫高品質的小說章節。

【最高優先原則｜內容與風格分離】
- 世界觀、人物、地名、專有名詞、設定與情節，**只能**來自本專案提供的「故事大綱」「角色卡」「世界設定」「前文摘要」與「寫作方向」。
- 「風格特徵」與「風格指南」**僅供模仿寫作技巧**（用詞、句式、節奏、語氣），**嚴禁**從中或任何外部作品借用任何人物、地名、專有名詞、設定或橋段。
- 若風格描述中意外出現任何具體專有名詞或情節，一律視為雜訊忽略，**絕不可**寫入正文。

【最高優先原則｜必須動筆，絕不拒寫】
- 「寫作方向」本身就是本章最核心的素材。即使「故事大綱」「角色卡」「世界設定」「前文摘要」等其他素材稀少或為空，你**也必須**依據「寫作方向」撰寫出完整的小說正文。
- 素材不足時，請在「寫作方向」的範圍內合理發揮、補足場景與細節，**絕不可**拒絕寫作。
- **嚴禁**輸出任何元說明或拒寫文字，例如「無法撰寫」「缺少以下素材」「無從得知」「請補充」「憑空捏造」等。你的輸出**只能**是小說正文本身。

【創作技巧與創意｜寫成「場景」，而非「大綱擴寫」】
- **場景化（Show, don't tell）**：把大綱裡的情節點轉化為有畫面、有動作的具體場景，**不要**平鋪直敘地複述或概述大綱。讓讀者「看見」事件發生，而非被「告知」發生了什麼。
- **感官沉浸**：調動視覺、聽覺、嗅覺、觸覺、味覺，讓場景可感可觸，避免空泛形容。
- **潛台詞與留白**：對話與敘事要有弦外之音，不要把情緒和意圖全部說破；適度留白讓讀者回味。
- **衝突與轉折**：每個場景盡量帶有內在衝突、張力或出人意料但合乎邏輯的小轉折，避免流水帳。
- **對話推動情節**：對話要揭示性格、推進劇情或製造衝突，避免無資訊量的寒暄。
- **避免陳腔濫調**：少用套話與老梗比喻，追求新鮮、具體、屬於這個故事的表達。
- **大膽而合理**：在不違反世界觀與角色性格的前提下，敢於做出有想像力的選擇，但轉折必須有鋪墊、說得通。

【篇幅與收尾｜務必寫完，不得中途斷尾】
- 本章目標篇幅約 **3000–4500 字**。請自行掌控節奏，在這個篇幅內寫出有完整「起承轉合」的章節。
- **務必寫到自然收尾**：結尾要落在一個完整的句子與段落上，可以是階段性的收束，也可以是刻意的懸念，但**絕對不能**在句子或場景寫到一半時突然中斷。
- 若篇幅將盡，請主動收攏情節、給出收尾，寧可縮短也不要寫成未完成的斷章。

【長篇連貫｜服務整體弧線，而非各自獨立】
- 本章是一部**中長篇小說**中的一章，不是獨立短篇。它必須服務整體故事弧線，朝「故事大綱」與下一個情節里程碑**推進**。
- **推進而非原地踏步**：本章結束時，處境、關係或資訊必須比開頭有所改變（新的衝突、賭注升高、關係質變、關鍵線索揭露）。嚴禁只是重複上一章的模式或把情節原地打轉。
- **不要提前解決主線**：核心衝突與最終高潮要留到全書後段。本章可以解決某個階段性小問題、回收某條支線，但**絕不可**過早化解故事的核心矛盾或讓主角輕易達成終極目標。
- **承先啟後**：承接前文已埋的伏筆與懸念，並為後續章節留下新的牽掛與發展空間，讓章節之間環環相扣。
- 參考「已達成的情節里程碑」，避免重複已經寫過的情節，把故事往尚未達成的方向推進。

請嚴格遵守以下10條規則：

1. **風格一致性**：根據「風格特徵」與「風格指南」模仿作者的語感——用詞習慣、句式結構、敘事節奏與語調，但**只學技巧、不抄內容**，不得照搬任何範例文字或參考作品中的具體元素。
2. **情節連貫性**：新內容必須與前文無縫銜接，不得出現邏輯斷層或矛盾。
3. **角色忠實度**：所有角色的言行必須符合其角色卡設定，包括性格、說話方式、背景等。
4. **世界觀遵守**：嚴格遵守本專案世界設定的規則，不得違反已建立的世界觀，也不得引入專案外的世界觀元素。
5. **大綱遵循**：把握故事大綱的核心方向推進情節，但**不要只是複述大綱**——要把大綱的情節點大膽地戲劇化、場景化，補足具體的細節、衝突與質感。
6. **節奏控制**：根據場景需求調整敘事節奏，場景描寫、對話、動作要交替穿插。
7. **伏筆布局**：適當埋設伏筆，為後續情節發展留下空間。
8. **情感層次**：注意角色的情感變化要有層次，避免突兀的情緒轉變。
9. **場景具體化**：場景描寫要具體生動，善用感官細節（視覺、聽覺、嗅覺、觸覺）。
10. **新角色引入規則**：如果需要引入新角色，必須通過自然的劇情發展引入，給予適當的外貌和性格描寫，並確保其出場有明確的劇情功能。不得無故引入與主線無關的角色。

請直接輸出完整的小說正文，從正文第一個字開始，不要包含章節標題或編號，也不要使用 JSON、程式碼區塊（```）或任何額外標記。"""


_CODE_FENCE_OPEN = re.compile(r"^```(?:json|JSON)?[ \t]*\n?")
_CODE_FENCE_CLOSE = re.compile(r"\n?```[ \t]*$")


def _clean_weaver_output(raw: str) -> tuple[str, Optional[int]]:
    """Extract clean novel prose from a Weaver response.

    Returns a ``(content, tokens_used)`` tuple where ``tokens_used`` is
    ``None`` unless the model returned a fully valid JSON object that included
    a numeric ``tokens_used`` field.

    The Weaver is instructed to return plain prose, but models sometimes wrap
    the text in a JSON object and/or a Markdown code fence, and long chapters
    frequently get truncated mid-JSON. This helper recovers clean prose in all
    of those cases so JSON/code scaffolding never leaks into the chapter body.
    """
    text = (raw or "").strip()
    if not text:
        return "", None

    # Strip Markdown code fences (terminated, or left open by truncation).
    text = _CODE_FENCE_OPEN.sub("", text)
    text = _CODE_FENCE_CLOSE.sub("", text)
    text = text.strip()

    # If the model still returned a JSON object, pull out the "content" value.
    if text.startswith("{") and '"content"' in text:
        try:
            obj = json.loads(text, strict=False)
            if isinstance(obj, dict) and isinstance(obj.get("content"), str):
                tokens = obj.get("tokens_used")
                tokens = int(tokens) if isinstance(tokens, (int, float)) else None
                return obj["content"].strip(), tokens
        except json.JSONDecodeError:
            # Truncated/invalid JSON: salvage the content string best-effort.
            match = re.search(r'"content"\s*:\s*"(.*)$', text, re.DOTALL)
            if match:
                value = match.group(1)
                # Drop a trailing incomplete ", "tokens_used": ... fragment.
                value = re.sub(r'"\s*,\s*"tokens_used".*$', "", value, flags=re.DOTALL)
                # Unescape the common JSON escape sequences.
                value = value.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
                return value.strip(), None

    return text, None


# High-precision markers of a meta-refusal (the model explaining why it will not
# write) rather than novel prose. These phrases are characteristic of an assistant
# declining a task and rarely appear in fiction, so matching a couple of them is a
# strong signal that the output is NOT a chapter body. Kept conservative on purpose
# to avoid false positives on legitimate prose that happens to contain e.g. "無法".
_REFUSAL_MARKERS = (
    "無法根據",
    "無法撰寫",
    "缺少以下",
    "必要素材",
    "無從得知",
    "無從掌握",
    "無從遵守",
    "無從確保",
    "無從模仿",
    "無從判斷",
    "請補充完整",
    "請補充",
    "憑空捏造",
    "重新提交",
    "最高原則",
)


def _looks_like_refusal(text: str) -> bool:
    """Return True if ``text`` reads like a meta-refusal rather than novel prose.

    A refusal is detected when the output is relatively short AND contains several
    refusal markers. The length guard prevents flagging a long, legitimate chapter
    that coincidentally mentions one of the marker phrases in dialogue.
    """
    stripped = (text or "").strip()
    if not stripped:
        return True  # empty output is treated as a failure to produce prose
    hits = sum(1 for marker in _REFUSAL_MARKERS if marker in stripped)
    if hits >= 2:
        return True
    # A single marker is only suspicious on a short, non-narrative blob.
    if hits == 1 and len(stripped) < 400:
        return True
    return False


class WeaverRefusalError(Exception):
    """Raised when the Weaver refuses to write instead of producing novel prose."""


STYLE_CONTROL_LABELS = {
    "narrative_pace": {
        "name": "敘事節奏",
        "low": "緩慢細膩，沉浸式描寫",
        "mid": "節奏適中，張弛有度",
        "high": "快節奏推進，簡潔有力",
    },
    "dialogue_style": {
        "name": "對話風格",
        "low": "書面化、文雅、含蓄",
        "mid": "自然平衡",
        "high": "口語化、生動、直白",
    },
    "description_density": {
        "name": "描寫密度",
        "low": "精簡留白，點到為止",
        "mid": "適度描寫",
        "high": "濃墨重彩，細緻入微",
    },
    "emotion_intensity": {
        "name": "情感強度",
        "low": "克制內斂，以行動暗示情感",
        "mid": "適度表達",
        "high": "濃烈外放，深入角色內心",
    },
    "action_detail": {
        "name": "動作場景",
        "low": "寫意式，注重氛圍",
        "mid": "適度展開",
        "high": "工筆細描，每一拳每一劍都有畫面",
    },
    "environment_desc": {
        "name": "環境描寫",
        "low": "簡略帶過，聚焦人物",
        "mid": "適度點綴",
        "high": "沉浸式場景構建，五感並用",
    },
}


def _format_style_controls(controls: dict) -> str:
    """
    Convert style_controls dict {key: 0-100} into natural language instructions
    for the Weaver agent.
    """
    if not controls:
        return ""

    instructions = []
    for key, value in controls.items():
        if key not in STYLE_CONTROL_LABELS:
            continue

        label = STYLE_CONTROL_LABELS[key]
        v = int(value) if isinstance(value, (int, float)) else 50

        if v <= 30:
            desc = label["low"]
        elif v >= 70:
            desc = label["high"]
        else:
            desc = label["mid"]

        instructions.append(f"- {label['name']}（{v}/100）：{desc}")

    if not instructions:
        return ""

    return "請根據以下風格控制參數調整寫作風格：\n" + "\n".join(instructions)


class Weaver(BaseAgent):
    """Generates chapter drafts based on direction, style, and context."""

    agent_name = "weaver"

    async def write(
        self,
        direction: str,
        style_features: dict,
        style_guide: str,
        plot_context: str,
        story_outline: str,
        previous_ending: str,
        character_cards: list[dict],
        world_settings: dict,
        previous_chapters_summary: str,
        milestones_progress: str = "",
        arc_plan_summary: str = "",
        writing_preferences: str = "",
        style_controls: dict | None = None,
    ) -> dict:
        """
        Generate a chapter draft.

        Args:
            direction: Writing direction/instructions for this chapter.
            style_features: Style profile dict from Profiler.
            style_guide: Content-free natural-language style guide (technique only).
            plot_context: Retrieved relevant plot context from vector store.
            story_outline: The overall story outline.
            previous_ending: The ending passage of the previous chapter.
            character_cards: List of character card dicts.
            world_settings: World-building settings dict.
            previous_chapters_summary: Summary of previous chapters.
            milestones_progress: Formatted "已達成里程碑" block (from
                arc_context.format_milestones_progress) giving the chapter a
                sense of the overall arc and what has already been accomplished.
            arc_plan_summary: Formatted "故事藍圖" block (from
                arc_context.format_arc_plan) describing the three-act structure,
                upcoming milestones and character arcs for the whole novel.
            writing_preferences: Editor-learned writing preferences for prompt injection.
            style_controls: Fine-grained style control parameters (sliders).

        Returns:
            dict with keys: content (str), tokens_used (int)
        """
        # Build user message with all context
        sections = []

        sections.append(f"## 寫作方向\n{direction}")

        if story_outline:
            sections.append(f"## 故事大綱\n{story_outline}")

        if arc_plan_summary:
            sections.append(arc_plan_summary)

        if previous_chapters_summary:
            sections.append(f"## 前文摘要\n{previous_chapters_summary}")

        if milestones_progress:
            sections.append(milestones_progress)

        if previous_ending:
            sections.append(f"## 上一章結尾\n{previous_ending}")

        if plot_context:
            sections.append(f"## 相關情節上下文\n{plot_context}")

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

        if style_features:
            sections.append(
                f"## 風格特徵\n{json.dumps(style_features, ensure_ascii=False, indent=2)}"
            )

        if style_guide:
            sections.append(
                "## 風格指南（僅供語感模仿，禁止借用任何內容）\n"
                "以下為本專案指定風格的寫作技巧摘要。請只模仿其用詞、句式、節奏與語氣，"
                "嚴禁從中借用任何人物、地名、專有名詞、設定或情節：\n\n"
                f"{style_guide}"
            )

        if writing_preferences:
            sections.append(f"## 寫作偏好（編輯學習所得）\n{writing_preferences}")

        if style_controls:
            sections.append(f"## 風格控制參數\n{_format_style_controls(style_controls)}")

        user_message = "\n\n".join(sections)
        user_message += (
            "\n\n請根據以上資訊撰寫本章內容，直接輸出正文，不要使用 JSON 或程式碼區塊。"
            "切記：本章要推動整體故事朝下一個里程碑前進、提升賭注，"
            "但不要提前解決核心衝突，並為後續章節留下懸念。"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.8,
            max_tokens=10000,
        )

        content, tokens_used = _clean_weaver_output(raw_response)

        if _looks_like_refusal(content):
            raise WeaverRefusalError(
                "模型拒絕撰寫本章正文（可能因專案素材不足）。"
                "請補充故事大綱、角色卡或世界設定，或提供更完整的寫作方向後再試一次。"
            )

        if tokens_used is None:
            tokens_used = len(content) // 4

        return {"content": content, "tokens_used": tokens_used}

    async def revise(
        self,
        current_content: str,
        logic_review: Optional[dict],
        style_review: Optional[dict],
        direction: str = "",
        style_features: Optional[dict] = None,
        style_guide: str = "",
        writing_preferences: str = "",
        style_controls: dict | None = None,
    ) -> dict:
        """
        Revise a chapter draft based on review feedback.

        Args:
            current_content: The current draft text to revise.
            logic_review: Logic review result from Chronicler.
            style_review: Style review result from Stylist.
            direction: Original writing direction.
            style_features: Style profile dict.
            style_guide: Content-free natural-language style guide (technique only).
            writing_preferences: Editor-learned preferences.
            style_controls: Fine-grained style control parameters.

        Returns:
            dict with keys: content (str), tokens_used (int)
        """
        sections = []

        sections.append(f"## 原始草稿\n{current_content}")

        if logic_review and logic_review.get("issues"):
            issues_text = json.dumps(logic_review["issues"], ensure_ascii=False, indent=2)
            sections.append(f"## 邏輯問題（需修正）\n{issues_text}")
            if logic_review.get("suggestions"):
                suggestions_text = json.dumps(logic_review["suggestions"], ensure_ascii=False, indent=2)
                sections.append(f"## 修正建議\n{suggestions_text}")

        if style_review and style_review.get("issues"):
            style_issues_text = json.dumps(style_review["issues"], ensure_ascii=False, indent=2)
            sections.append(f"## 風格問題（需修正）\n{style_issues_text}")

        if style_features:
            sections.append(
                f"## 目標風格特徵\n{json.dumps(style_features, ensure_ascii=False, indent=2)}"
            )

        if style_guide:
            sections.append(
                "## 風格指南（僅供語感模仿，禁止借用任何內容）\n"
                "只模仿其用詞、句式、節奏與語氣，嚴禁借用任何人物、地名、專有名詞、設定或情節：\n\n"
                f"{style_guide}"
            )

        if writing_preferences:
            sections.append(f"## 寫作偏好\n{writing_preferences}")

        if style_controls:
            sections.append(f"## 風格控制參數\n{_format_style_controls(style_controls)}")

        user_message = "\n\n".join(sections)
        user_message += "\n\n請根據以上審查意見修改草稿，保持原有情節方向，修正指出的問題，直接輸出修改後的正文，不要使用 JSON 或程式碼區塊。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=10000,
        )

        content, tokens_used = _clean_weaver_output(raw_response)

        # A refusing revision must never erase a good draft — keep the original.
        if _looks_like_refusal(content):
            logger.warning(
                "Weaver.revise returned a refusal; keeping the existing draft unchanged"
            )
            return {"content": current_content, "tokens_used": 0}

        if tokens_used is None:
            tokens_used = len(content) // 4

        return {"content": content, "tokens_used": tokens_used}
