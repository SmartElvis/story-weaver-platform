"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { Loader2, Sparkles, Map } from "lucide-react";
import type { Chapter, ArcPlan } from "@/types/project";

const MDEditor = dynamic(
  () => import("@uiw/react-md-editor").then((mod) => mod.default),
  { ssr: false, loading: () => <div className="h-64 bg-gray-100 rounded-lg animate-pulse" /> }
);

interface OutlineTabProps {
  outlineContent: string;
  setOutlineContent: (v: string) => void;
  onSave: () => void;
  chapters: Chapter[];
  arcPlan: ArcPlan | null;
  generatingArcPlan: boolean;
  onGenerateArcPlan: () => void;
}

export function OutlineTab({
  outlineContent,
  setOutlineContent,
  onSave,
  chapters,
  arcPlan,
  generatingArcPlan,
  onGenerateArcPlan,
}: OutlineTabProps) {
  const [isEditing, setIsEditing] = useState(false);

  // Build auto-generated outline from finalized chapters with summaries
  const finalizedChapters = chapters.filter((c) => c.status === "FINALIZED");
  const autoOutline = finalizedChapters
    .map((c) => {
      const summary =
        c.extraction_result &&
        (c.extraction_result as Record<string, unknown>).chapter_summary
          ? String((c.extraction_result as Record<string, unknown>).chapter_summary)
          : "";
      return `### 第${c.chapter_number}章 — ${c.title || "無標題"}\n${summary || "（摘要尚未生成）"}`;
    })
    .join("\n\n");

  const hasManualOutline = outlineContent.trim().length > 0;
  const hasArcPlan = !!arcPlan && ((arcPlan.milestones?.length ?? 0) > 0 || !!arcPlan.theme);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Manual outline section */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">故事大綱</h2>
          {isEditing ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => {
                  onSave();
                  setIsEditing(false);
                }}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
              >
                儲存大綱
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className="px-4 py-2 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
            >
              {hasManualOutline ? "編輯大綱" : "撰寫自定義大綱"}
            </button>
          )}
        </div>

        {isEditing ? (
          <div data-color-mode="light">
            <MDEditor
              value={outlineContent}
              onChange={(val) => setOutlineContent(val || "")}
              height={400}
              preview="edit"
            />
          </div>
        ) : hasManualOutline ? (
          <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
            {outlineContent}
          </div>
        ) : (
          <p className="text-sm text-gray-400">
            尚未撰寫自定義大綱。點擊「撰寫自定義大綱」開始編輯，或參考下方自動生成的章節摘要。
          </p>
        )}
      </div>

      {/* Story blueprint (arc plan) section */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Map className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-gray-900">故事藍圖</h2>
            <span className="text-xs text-gray-400">AI 架構・自動維護</span>
          </div>
          <button
            onClick={onGenerateArcPlan}
            disabled={generatingArcPlan}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {generatingArcPlan ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                生成中…
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                {hasArcPlan ? "重新生成藍圖" : "生成故事藍圖"}
              </>
            )}
          </button>
        </div>

        {generatingArcPlan && !hasArcPlan ? (
          <div className="flex items-center gap-3 text-sm text-gray-500 bg-gray-50 rounded-lg p-4">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在根據大綱規劃三幕結構與里程碑，約需數十秒…
          </div>
        ) : hasArcPlan ? (
          <ArcPlanView plan={arcPlan as ArcPlan} />
        ) : (
          <p className="text-sm text-gray-400">
            尚未生成故事藍圖。藍圖會規劃三幕結構、關鍵里程碑（含目標章節）與角色弧線，
            讓每一章都朝整體故事推進，而非各自獨立。建議先撰寫大綱再生成。
          </p>
        )}
      </div>

      {/* Auto-generated outline */}
      {autoOutline && finalizedChapters.length > 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-6">
          <h3 className="text-base font-semibold text-gray-800 mb-4">
            已完成章節摘要 (自動生成)
          </h3>
          <div className="space-y-4">
            {finalizedChapters.map((c) => {
              const summary =
                c.extraction_result &&
                (c.extraction_result as Record<string, unknown>).chapter_summary
                  ? String((c.extraction_result as Record<string, unknown>).chapter_summary)
                  : "";
              return (
                <div
                  key={c.id}
                  className="bg-white border border-gray-100 rounded-lg p-4"
                >
                  <h4 className="font-semibold text-gray-900 mb-2">
                    第{c.chapter_number}章 — {c.title || "無標題"}
                  </h4>
                  <p className="text-sm text-gray-600 leading-relaxed">
                    {summary || "（摘要尚未生成）"}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Read-only arc plan rendering ---

function ArcPlanView({ plan }: { plan: ArcPlan }) {
  const milestones = plan.milestones || [];
  const achievedCount = milestones.filter((m) => m.status === "achieved").length;

  return (
    <div className="space-y-6">
      {/* Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {plan.theme && (
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-xs font-medium text-gray-500 mb-1">核心主題</div>
            <div className="text-sm text-gray-800">{plan.theme}</div>
          </div>
        )}
        {plan.central_conflict && (
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-xs font-medium text-gray-500 mb-1">核心衝突</div>
            <div className="text-sm text-gray-800">{plan.central_conflict}</div>
          </div>
        )}
      </div>

      {typeof plan.total_chapters === "number" && plan.total_chapters > 0 && (
        <div className="text-sm text-gray-600">
          預估總章數：<span className="font-semibold text-gray-900">約 {plan.total_chapters} 章</span>
          {milestones.length > 0 && (
            <span className="ml-4">
              里程碑進度：
              <span className="font-semibold text-indigo-600">
                {" "}{achievedCount} / {milestones.length}
              </span>
            </span>
          )}
          {typeof plan.updated_at_chapter === "number" && plan.updated_at_chapter > 0 && (
            <span className="ml-4 text-gray-400">（已更新至第 {plan.updated_at_chapter} 章）</span>
          )}
        </div>
      )}

      {/* Acts */}
      {(plan.acts?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">階段結構</h4>
          <div className="space-y-2">
            {plan.acts!.map((act, idx) => (
              <div key={idx} className="flex items-start gap-3 border border-gray-100 rounded-lg p-3">
                <span className="shrink-0 text-xs font-medium text-indigo-600 bg-indigo-50 rounded px-2 py-1">
                  {act.chapter_range || `第${idx + 1}階段`}
                </span>
                <div>
                  <div className="text-sm font-medium text-gray-900">{act.name}</div>
                  {act.goal && <div className="text-sm text-gray-500">{act.goal}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Milestones */}
      {milestones.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">關鍵里程碑</h4>
          <div className="space-y-2">
            {milestones.map((m) => {
              const achieved = m.status === "achieved";
              return (
                <div key={m.id} className="flex items-start gap-3 border border-gray-100 rounded-lg p-3">
                  <span
                    className={`shrink-0 text-xs font-medium rounded px-2 py-1 ${
                      achieved
                        ? "text-green-700 bg-green-50"
                        : "text-amber-700 bg-amber-50"
                    }`}
                  >
                    {achieved ? `已達成${m.achieved_chapter ? `・第${m.achieved_chapter}章` : ""}` : "待推進"}
                  </span>
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-900">
                      {m.title}
                      {typeof m.target_chapter === "number" && (
                        <span className="ml-2 text-xs text-gray-400">目標第 {m.target_chapter} 章</span>
                      )}
                    </div>
                    {m.description && <div className="text-sm text-gray-500">{m.description}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Character arcs */}
      {(plan.character_arcs?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">角色弧線</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {plan.character_arcs!.map((arc, idx) => (
              <div key={idx} className="border border-gray-100 rounded-lg p-3">
                <div className="text-sm font-medium text-gray-900 mb-1">{arc.name}</div>
                {(arc.want || arc.need) && (
                  <div className="text-sm text-gray-500">
                    {arc.want && <>想要「{arc.want}」</>}
                    {arc.want && arc.need && "，"}
                    {arc.need && <>實則需要「{arc.need}」</>}
                  </div>
                )}
                {arc.transformation && (
                  <div className="text-sm text-gray-400 mt-1">轉變：{arc.transformation}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Subplots */}
      {(plan.subplots?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">支線</h4>
          <div className="space-y-2">
            {plan.subplots!.map((sp, idx) => (
              <div key={idx} className="border border-gray-100 rounded-lg p-3">
                <div className="text-sm font-medium text-gray-900">
                  {sp.name}
                  {sp.status && (
                    <span className="ml-2 text-xs text-gray-400">({sp.status})</span>
                  )}
                </div>
                {sp.summary && <div className="text-sm text-gray-500">{sp.summary}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
