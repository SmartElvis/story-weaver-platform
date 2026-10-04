"""
Profiler Agent (風格分析師)
Analyzes writing style from text chunks and returns a structured style profile.
"""

import json

from app.agents.base import BaseAgent

SYSTEM_PROMPT = """你是一位專業的文學風格分析師（風格分析師）。你的任務是深入分析提供的文本片段，提取作者的獨特寫作風格特徵。

【最高原則｜只分析「怎麼寫」，絕不記錄「寫了什麼」】
- 所有欄位（包含 style_guide）都只能描述可遷移的「寫作技巧」：用詞習慣、句式與節奏、修辭手法、敘事視角與時態、語氣與情感強度等。
- 嚴禁在任何欄位中出現參考文本的具體內容：不得包含任何人物名稱、地名、機構或專有名詞、具體情節事件、對白內容、或世界觀設定。
- frequent_phrases 只收錄「結構性／習慣性表達」（如連接詞、語氣詞、慣用句式框架），不得收錄帶有劇情或專有名詞的短語。
- overall_mood、description_style 等描述只可用抽象形容詞（如「冷峻」「克制」「細膩」「意識流」），不得綁定任何具體場景、時代或設定。

請從以下六個部分進行分析，並以JSON格式回傳結果：

1. **lexicon（詞彙特徵）**：
   - frequent_phrases: 作者常用的短語或表達方式（列出5-10個）
   - vocabulary_level: 詞彙難度等級（simple/moderate/advanced/literary）
   - dialect_features: 方言或地域性語言特徵

2. **syntax（句法特徵）**：
   - avg_sentence_length: 平均句子長度描述（short/medium/long/mixed）
   - sentence_patterns: 常見句式模式（列出3-5個特徵）
   - paragraph_structure: 段落結構特點

3. **rhetoric（修辭特徵）**：
   - figurative_devices: 常用修辭手法（比喻、擬人、誇張等）
   - dialogue_style: 對話風格特點
   - description_style: 描寫風格（細膩/簡潔/意識流等）

4. **narrative（敘事特徵）**：
   - pov: 敘事視角（first_person/third_limited/third_omniscient/second_person）
   - tense: 主要時態（past/present/mixed）
   - pacing: 節奏特點（fast/moderate/slow/varied）
   - scene_transition: 場景轉換方式

5. **tone（語調特徵）**：
   - overall_mood: 整體氛圍
   - humor_level: 幽默程度（none/subtle/moderate/heavy）
   - emotional_intensity: 情感強度（restrained/moderate/intense）

6. **style_guide（風格指南）**：一段150-300字的自然語言寫作指南，說明「如何」以這位作者的風格寫作，涵蓋用詞習慣、句子長短與節奏、對白與敘述的比例、描寫與意象的密度、敘事節奏、視角、情感語調等可遷移的寫作技巧。
   ⚠️ 硬性要求：style_guide 只描述「寫作技巧」，嚴禁包含任何故事內容——不得出現任何人物名稱、地名、專有名詞、具體情節事件或世界觀設定。只寫「怎麼寫」，絕不寫「寫了什麼」。

請嚴格以JSON格式回傳，不要包含任何其他解釋文字。"""


MERGE_SYSTEM_PROMPT = """你是一位專業的文學風格分析師。下方是對「同一位作者」多段不同文本分別做出的風格分析結果（一個 JSON 陣列）。請綜合歸納，提煉出貫穿全部樣本、穩定且具代表性的寫作風格，捨棄僅出現在單一樣本的偶發特徵，並以與單次分析完全相同的 JSON 結構（lexicon/syntax/rhetoric/narrative/tone/style_guide）回傳一份整合後的風格檔案。

【最高原則｜只描述「怎麼寫」，絕不記錄「寫了什麼」】
- 所有欄位與 style_guide 都只能描述可遷移的寫作技巧（用詞、句式、節奏、修辭、視角、時態、語氣、情感強度等）。
- 嚴禁出現任何人物名稱、地名、專有名詞、具體情節、對白內容或世界觀設定。
- style_guide 須為一段150-300字、內容無關的自然語言寫作指南。

請嚴格以JSON格式回傳，不要包含任何其他解釋文字。"""


class Profiler(BaseAgent):
    """Analyzes writing style from text chunks and produces a style profile."""

    agent_name = "profiler"

    async def analyze(self, text_chunks: list[str]) -> dict:
        """
        Analyze writing style from a list of text chunks.

        Args:
            text_chunks: List of text samples to analyze.

        Returns:
            dict with keys: lexicon, syntax, rhetoric, narrative, tone, style_guide
        """
        combined_text = "\n\n---\n\n".join(text_chunks)
        user_message = f"請分析以下文本片段的寫作風格：\n\n{combined_text}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=3000,
        )

        result = self._parse_json_response(raw_response)
        return self._fill_defaults(result)

    async def merge_profiles(self, profiles: list[dict]) -> dict:
        """Synthesize multiple per-batch style analyses into one consolidated profile.

        This is the reduce step of map-reduce profiling: each input profile was
        produced by :meth:`analyze` over a different slice of the same author's
        corpus. The merge keeps stable, corpus-wide traits and discards one-off
        artifacts, returning the same schema as :meth:`analyze`.
        """
        user_message = (
            "請綜合以下多份風格分析，產出一份整合後的風格檔案：\n\n"
            + json.dumps(profiles, ensure_ascii=False, indent=2)
        )
        messages = [
            {"role": "system", "content": MERGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_response = await self.llm.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=3000,
        )

        result = self._parse_json_response(raw_response)
        return self._fill_defaults(result)

    @staticmethod
    def _fill_defaults(result: dict) -> dict:
        """Back-fill any missing top-level/sub-keys with safe default values."""
        default_structure = {
            "lexicon": {
                "frequent_phrases": [],
                "vocabulary_level": "moderate",
                "dialect_features": [],
            },
            "syntax": {
                "avg_sentence_length": "medium",
                "sentence_patterns": [],
                "paragraph_structure": "",
            },
            "rhetoric": {
                "figurative_devices": [],
                "dialogue_style": "",
                "description_style": "",
            },
            "narrative": {
                "pov": "third_limited",
                "tense": "past",
                "pacing": "moderate",
                "scene_transition": "",
            },
            "tone": {
                "overall_mood": "",
                "humor_level": "subtle",
                "emotional_intensity": "moderate",
            },
            "style_guide": "",
        }

        for key, default_val in default_structure.items():
            if key not in result:
                result[key] = default_val
            elif isinstance(default_val, dict) and isinstance(result.get(key), dict):
                for sub_key, sub_val in default_val.items():
                    if sub_key not in result[key]:
                        result[key][sub_key] = sub_val

        return result
