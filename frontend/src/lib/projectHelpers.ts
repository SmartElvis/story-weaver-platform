// --- Helpers ---

export function statusLabel(status: string): { text: string; color: string } {
  switch (status) {
    case "FINALIZED":
      return { text: "已定稿", color: "bg-green-100 text-green-700" };
    case "DRAFTING":
      return { text: "生成中", color: "bg-yellow-100 text-yellow-700" };
    case "REVIEW":
      return { text: "可編輯", color: "bg-blue-100 text-blue-700" };
    case "REVISION":
      return { text: "修訂中", color: "bg-orange-100 text-orange-700" };
    default:
      return { text: "可編輯", color: "bg-gray-100 text-gray-600" };
  }
}

export function tensionColor(tension: string): string {
  switch (tension) {
    case "rising":
      return "text-orange-600";
    case "climax":
      return "text-red-600";
    case "falling":
      return "text-blue-600";
    default:
      return "text-gray-600";
  }
}

export const STYLE_CONTROL_DEFS = [
  { key: "narrative_pace", label: "敘事節奏", left: "緩慢細膩", right: "快節奏推進" },
  { key: "dialogue_style", label: "對話風格", left: "書面文雅", right: "口語生動" },
  { key: "description_density", label: "描寫密度", left: "精簡留白", right: "濃墨重彩" },
  { key: "emotion_intensity", label: "情感強度", left: "克制內斂", right: "濃烈外放" },
  { key: "action_detail", label: "動作場景", left: "寫意氛圍", right: "工筆細描" },
  { key: "environment_desc", label: "環境描寫", left: "簡略帶過", right: "沉浸五感" },
];
