"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  BookOpen,
  Loader2,
  Sparkles,
  CheckCircle2,
  GitBranch,
  Pencil,
  Languages,
} from "lucide-react";
import type { Chapter, ForeseerBranch, ForeseerResult } from "@/types/project";
import { tensionColor } from "@/lib/projectHelpers";

const MDEditor = dynamic(
  () => import("@uiw/react-md-editor").then((mod) => mod.default),
  { ssr: false, loading: () => <div className="h-64 bg-gray-100 rounded-lg animate-pulse" /> }
);

interface EditorTabProps {
  selectedChapter: Chapter | null;
  editorContent: string;
  setEditorContent: (v: string) => void;
  generating: boolean;
  finalizing: boolean;
  convertingScript: boolean;
  onGenerate: () => void;
  onFinalize: () => void;
  onSave: () => void;
  onRenameTitle: (title: string) => void;
  onCreateFromBranch: (branch: ForeseerBranch) => void;
  onConvertScript: (target: "simplified" | "traditional") => void;
}

export function EditorTab({
  selectedChapter,
  editorContent,
  setEditorContent,
  generating,
  finalizing,
  convertingScript,
  onGenerate,
  onFinalize,
  onSave,
  onRenameTitle,
  onCreateFromBranch,
  onConvertScript,
}: EditorTabProps) {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  if (!selectedChapter) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400">
        <BookOpen className="w-16 h-16 mb-4 text-gray-300" />
        <p className="text-lg">選擇一個章節開始編輯</p>
        <p className="text-sm mt-1">或建立新章節</p>
      </div>
    );
  }

  const logicScore = selectedChapter.logic_review
    ? (selectedChapter.logic_review as Record<string, unknown>).overall_score
    : null;
  const styleScore = selectedChapter.style_review
    ? (selectedChapter.style_review as Record<string, unknown>).overall_score
    : null;

  const suggestion = selectedChapter.next_chapter_suggestion as ForeseerResult | null;

  return (
    <div className="p-6 space-y-6">
      {/* Chapter Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <span>第 {selectedChapter.chapter_number} 章</span>
            {isEditingTitle ? (
              <input
                autoFocus
                type="text"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                onBlur={() => {
                  onRenameTitle(titleDraft.trim());
                  setIsEditingTitle(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    onRenameTitle(titleDraft.trim());
                    setIsEditingTitle(false);
                  } else if (e.key === "Escape") {
                    setIsEditingTitle(false);
                  }
                }}
                placeholder="輸入章節標題"
                className="text-base font-normal text-gray-700 border border-gray-300 rounded-md px-2 py-0.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            ) : (
              <button
                onClick={() => {
                  setTitleDraft(selectedChapter.title || "");
                  setIsEditingTitle(true);
                }}
                className="flex items-center gap-1 text-base font-normal text-gray-500 hover:text-indigo-600 transition-colors"
                title="修改章節標題"
              >
                <span>{selectedChapter.title || "設定標題"}</span>
                <Pencil className="w-3.5 h-3.5" />
              </button>
            )}
          </h2>
        </div>
        <div className="flex items-center gap-4 text-sm">
          {logicScore !== null && logicScore !== undefined && (
            <div className="flex items-center gap-1.5">
              <span className="text-gray-500">通順分數</span>
              <span className="font-semibold text-indigo-600">
                {String(logicScore)}
              </span>
            </div>
          )}
          {styleScore !== null && styleScore !== undefined && (
            <div className="flex items-center gap-1.5">
              <span className="text-gray-500">風格分數</span>
              <span className="font-semibold text-purple-600">
                {String(styleScore)}
              </span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <span className="text-gray-500">修訂次數</span>
            <span className="font-semibold text-gray-700">
              {selectedChapter.revision_count}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-gray-500">Token</span>
            <span className="font-semibold text-gray-700">
              {selectedChapter.tokens_used.toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Editor Area */}
      <div className="relative">
        {(generating || finalizing) && (
          <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex items-center justify-center rounded-lg">
            <div className="flex items-center gap-3">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
              <span className="text-gray-700 font-medium">
                {generating ? "生成中..." : "定稿中..."}
              </span>
            </div>
          </div>
        )}
        <div data-color-mode="light">
          <MDEditor
            value={editorContent}
            onChange={(val) => setEditorContent(val || "")}
            height={400}
            preview="edit"
          />
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={onGenerate}
          disabled={generating || finalizing}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {generating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          AI 生成
        </button>
        <button
          onClick={onFinalize}
          disabled={
            generating ||
            finalizing ||
            selectedChapter.status === "FINALIZED" ||
            !selectedChapter.draft_content
          }
          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {finalizing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <CheckCircle2 className="w-4 h-4" />
          )}
          定稿
        </button>
        <button
          onClick={onSave}
          disabled={generating || finalizing}
          className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          儲存草稿
        </button>

        {/* Script conversion - only for finalized chapters */}
        {selectedChapter.status === "FINALIZED" && (
          <div className="flex items-center gap-2 ml-auto border-l border-gray-200 pl-3">
            <Languages className="w-4 h-4 text-gray-400" />
            <button
              onClick={() => onConvertScript("simplified")}
              disabled={convertingScript || generating || finalizing}
              className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {convertingScript ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                "轉為簡體"
              )}
            </button>
            <button
              onClick={() => onConvertScript("traditional")}
              disabled={convertingScript || generating || finalizing}
              className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {convertingScript ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                "轉為繁體"
              )}
            </button>
          </div>
        )}
      </div>

      {/* Foreseer - Next Chapter Suggestions */}
      {suggestion && suggestion.branches && suggestion.branches.length > 0 && (
        <div className="mt-8 border border-gray-200 rounded-xl bg-white p-6">
          <div className="flex items-center gap-2 mb-4">
            <GitBranch className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-semibold text-gray-900">
              下一章發展參考
            </h3>
          </div>

          {suggestion.overall_assessment && (
            <p className="text-sm text-gray-600 mb-4 bg-gray-50 p-3 rounded-lg">
              {suggestion.overall_assessment}
            </p>
          )}

          <h4 className="text-sm font-semibold text-gray-700 mb-3">情節分支</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {suggestion.branches.map((branch, idx) => (
              <div
                key={idx}
                className="border border-gray-200 rounded-lg p-4 hover:border-indigo-300 hover:shadow-sm transition-all"
              >
                <h5 className="font-semibold text-gray-900 mb-2">
                  {branch.title}
                </h5>
                <p className="text-sm text-gray-600 mb-3 line-clamp-3">
                  {branch.summary}
                </p>
                <div className="flex items-center gap-3 mb-3 text-xs">
                  <span className={`font-medium ${tensionColor(branch.tension)}`}>
                    張力: {branch.tension}
                  </span>
                  {branch.new_characters && branch.new_characters.length > 0 && (
                    <span className="text-green-600">
                      + {branch.new_characters.join(", ")}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => onCreateFromBranch(branch)}
                  className="w-full text-center py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-md hover:bg-indigo-50 transition-colors"
                >
                  + 建立下一章
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
