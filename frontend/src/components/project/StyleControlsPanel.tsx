"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { STYLE_CONTROL_DEFS } from "@/lib/projectHelpers";

interface StyleControlsPanelProps {
  controls: Record<string, number> | null;
  onUpdate: (controls: Record<string, number>) => void;
}

export function StyleControlsPanel({
  controls,
  onUpdate,
}: StyleControlsPanelProps) {
  const [localControls, setLocalControls] = useState<Record<string, number>>(() => {
    const defaults: Record<string, number> = {};
    STYLE_CONTROL_DEFS.forEach((d) => {
      defaults[d.key] = controls?.[d.key] ?? 50;
    });
    return defaults;
  });
  const [dirty, setDirty] = useState(false);

  // Sync from props when controls change externally
  useEffect(() => {
    if (controls) {
      setLocalControls((prev) => {
        const next = { ...prev };
        STYLE_CONTROL_DEFS.forEach((d) => {
          if (controls[d.key] !== undefined) {
            next[d.key] = controls[d.key];
          }
        });
        return next;
      });
    }
  }, [controls]);

  const handleSliderChange = (key: string, value: number) => {
    setLocalControls((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const handleSave = () => {
    onUpdate(localControls);
    setDirty(false);
  };

  const handleReset = () => {
    const defaults: Record<string, number> = {};
    STYLE_CONTROL_DEFS.forEach((d) => {
      defaults[d.key] = 50;
    });
    setLocalControls(defaults);
    setDirty(true);
  };

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-500" />
          <h3 className="text-base font-semibold text-gray-900">風格控制</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="text-sm text-gray-500 hover:text-gray-700 border border-gray-200 px-3 py-1 rounded-md hover:bg-gray-50 transition-colors"
          >
            重置為預設
          </button>
          {dirty && (
            <button
              onClick={handleSave}
              className="text-sm text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-1 rounded-md transition-colors"
            >
              保存
            </button>
          )}
        </div>
      </div>
      <p className="text-sm text-gray-500 mb-5">
        調整滑桿來控制 AI 生成的寫作風格。這些設定會在生成和修訂時自動套用。
      </p>
      <div className="space-y-5">
        {STYLE_CONTROL_DEFS.map((def) => (
          <div key={def.key}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-medium text-gray-700">{def.label}</span>
              <span className="text-xs text-indigo-600 font-mono bg-indigo-50 px-1.5 py-0.5 rounded">
                {localControls[def.key]}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400 w-16 text-right shrink-0">{def.left}</span>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={localControls[def.key]}
                onChange={(e) => handleSliderChange(def.key, Number(e.target.value))}
                className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
              <span className="text-xs text-gray-400 w-16 shrink-0">{def.right}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
