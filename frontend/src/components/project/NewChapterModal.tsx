"use client";

import { X } from "lucide-react";

interface NewChapterModalProps {
  tab: "ai" | "manual";
  setTab: (t: "ai" | "manual") => void;
  title: string;
  setTitle: (v: string) => void;
  direction: string;
  setDirection: (v: string) => void;
  content: string;
  setContent: (v: string) => void;
  onClose: () => void;
  onCreate: () => void;
}

export function NewChapterModal({
  tab,
  setTab,
  title,
  setTitle,
  direction,
  setDirection,
  content,
  setContent,
  onClose,
  onCreate,
}: NewChapterModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">新建章節</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setTab("ai")}
            className={`flex-1 py-3 text-sm font-medium text-center transition-colors ${
              tab === "ai"
                ? "text-indigo-600 border-b-2 border-indigo-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            AI 生成
          </button>
          <button
            onClick={() => setTab("manual")}
            className={`flex-1 py-3 text-sm font-medium text-center transition-colors ${
              tab === "manual"
                ? "text-indigo-600 border-b-2 border-indigo-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            手動輸入
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              章節標題（選填）
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="例如：廢墟啟程"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              本章情節方向
            </label>
            <textarea
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
              placeholder="描述這一章的主要情節方向、核心事件..."
            />
          </div>

          {tab === "manual" && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  章節內容
                </label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
                  placeholder="直接輸入章節內容..."
                />
              </div>
              <p className="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">
                內容將直接保存為草稿，跳過 AI 生成。建立後可編輯並定稿。
              </p>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
          <button
            onClick={onCreate}
            disabled={!direction.trim()}
            className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {tab === "ai" ? "建立並生成" : "建立章節"}
          </button>
        </div>
      </div>
    </div>
  );
}
