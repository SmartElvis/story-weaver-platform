"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import toast from "react-hot-toast";
import {
  ArrowLeft,
  Plus,
  Loader2,
  ChevronDown,
  Download,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type {
  Chapter,
  Project,
  StyleProfile,
  ForeseerBranch,
} from "@/types/project";
import { statusLabel } from "@/lib/projectHelpers";
import { EditorTab } from "@/components/project/EditorTab";
import { OutlineTab } from "@/components/project/OutlineTab";
import { SettingsTab } from "@/components/project/SettingsTab";
import { NewChapterModal } from "@/components/project/NewChapterModal";

// --- Main Component ---

export default function ProjectEditorPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { ready } = useAuth();
  const mountedRef = useRef(true);

  // Core data (managed by SWR)
  const { data: project = null, mutate: mutateProject } = useSWR<Project>(
    ready ? ["project", projectId] : null,
    () => api.getProject(projectId),
    { onError: () => toast.error("無法載入專案") }
  );
  const { data: chapters = [], mutate: mutateChapters } = useSWR<Chapter[]>(
    ready ? ["chapters", projectId] : null,
    () => api.listChapters(projectId),
    { onError: () => toast.error("無法載入章節") }
  );
  const { data: styles = [] } = useSWR<StyleProfile[]>(
    ready ? "styles" : null,
    () => api.listStyles()
  );
  const loading = ready && (!project || !chapters);

  // UI state
  const [activeTab, setActiveTab] = useState<"editor" | "outline" | "settings">("editor");
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [showNewChapterModal, setShowNewChapterModal] = useState(false);
  const [newChapterTab, setNewChapterTab] = useState<"ai" | "manual">("ai");
  const [newChapterDirection, setNewChapterDirection] = useState("");
  const [newChapterTitle, setNewChapterTitle] = useState("");
  const [newChapterContent, setNewChapterContent] = useState("");
  const [editorContent, setEditorContent] = useState<string>("");
  const [outlineContent, setOutlineContent] = useState<string>("");
  const [showStyleDropdown, setShowStyleDropdown] = useState(false);
  const [showCharJsonView, setShowCharJsonView] = useState(false);
  const [showExportDropdown, setShowExportDropdown] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [generatingArcPlan, setGeneratingArcPlan] = useState(false);
  const [convertingScript, setConvertingScript] = useState(false);

  const selectedChapter = chapters.find((c) => c.id === selectedChapterId) || null;
  const activeStyle = styles.find((s) => s.id === project?.active_style_id) || null;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Seed the outline editor once the project's outline is loaded.
  useEffect(() => {
    if (project) {
      setOutlineContent(project.outline || "");
    }
  }, [project]);

  // Update editor content ONLY when the user switches to a different chapter.
  // Using selectedChapterId (a stable string) instead of selectedChapter (a new
  // object reference on every SWR refresh) prevents overwriting unsaved edits.
  const loadedChapterIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (selectedChapterId && selectedChapterId !== loadedChapterIdRef.current) {
      loadedChapterIdRef.current = selectedChapterId;
      const chapter = chapters.find((c) => c.id === selectedChapterId);
      if (chapter) {
        setEditorContent(chapter.draft_content || chapter.final_content || "");
      }
    }
  }, [selectedChapterId, chapters]);

  // --- Polling for generation status ---

  const pollChapter = useCallback(
    async (chapterId: string, expectedStatuses: string[]) => {
      const maxAttempts = 60;
      let attempts = 0;
      const poll = async (): Promise<void> => {
        attempts++;
        if (attempts > maxAttempts) {
          toast.error("操作超時，請手動重新整理");
          setGenerating(false);
          setFinalizing(false);
          return;
        }
        try {
          const chapter = await api.getChapter(projectId, chapterId);
          if (!mountedRef.current) return;
          if (expectedStatuses.includes(chapter.status)) {
            // Update editor with fresh content from the completed operation
            if (chapterId === loadedChapterIdRef.current) {
              setEditorContent(chapter.draft_content || chapter.final_content || "");
            }
            await mutateChapters();
            await mutateProject();
            setGenerating(false);
            setFinalizing(false);
            toast.success("操作完成");
            return;
          }
          // Check for error in logic_review
          if (chapter.logic_review && (chapter.logic_review as Record<string, unknown>).error) {
            toast.error(`錯誤: ${(chapter.logic_review as Record<string, unknown>).error}`);
            setGenerating(false);
            setFinalizing(false);
            await mutateChapters();
            return;
          }
        } catch {
          // continue polling
        }
        if (mountedRef.current) setTimeout(poll, 3000);
      };
      await poll();
    },
    [projectId, mutateChapters, mutateProject]
  );

  // --- Actions ---

  const handleGenerate = async () => {
    if (!selectedChapterId) return;
    setGenerating(true);
    try {
      await api.generateChapter(projectId, selectedChapterId);
      toast("AI 生成已啟動...", { icon: "🤖" });
      pollChapter(selectedChapterId, ["REVIEW", "REVISION"]);
    } catch {
      toast.error("生成失敗");
      setGenerating(false);
    }
  };

  const handleFinalize = async () => {
    if (!selectedChapterId) return;
    setFinalizing(true);
    try {
      await api.finalizeChapter(projectId, selectedChapterId);
      toast("定稿流程已啟動...", { icon: "✅" });
      pollChapter(selectedChapterId, ["FINALIZED"]);
    } catch {
      toast.error("定稿失敗");
      setFinalizing(false);
    }
  };

  const handleCreateChapter = async () => {
    const nextNumber = chapters.length > 0 ? Math.max(...chapters.map((c) => c.chapter_number)) + 1 : 1;
    try {
      const payload: {
        chapter_number: number;
        title?: string;
        direction?: string;
        user_content?: string;
      } = {
        chapter_number: nextNumber,
      };

      if (newChapterTitle.trim()) {
        payload.title = newChapterTitle.trim();
      }

      if (newChapterTab === "ai") {
        payload.direction = newChapterDirection;
      } else {
        payload.direction = newChapterDirection;
        if (newChapterContent.trim()) {
          payload.user_content = newChapterContent;
        }
      }

      const created = await api.createChapter(projectId, payload);
      await mutateChapters();
      setSelectedChapterId(created.id);
      setShowNewChapterModal(false);
      setNewChapterDirection("");
      setNewChapterTitle("");
      setNewChapterContent("");

      // If AI tab, trigger generation
      if (newChapterTab === "ai") {
        setGenerating(true);
        try {
          await api.generateChapter(projectId, created.id);
          toast("AI 生成已啟動...", { icon: "🤖" });
          pollChapter(created.id, ["REVIEW", "REVISION"]);
        } catch {
          toast.error("生成啟動失敗");
          setGenerating(false);
        }
      } else {
        toast.success("章節已建立");
      }
    } catch {
      toast.error("建立章節失敗");
    }
  };

  const handleSaveContent = async () => {
    if (!selectedChapterId) return;
    try {
      await api.updateChapter(projectId, selectedChapterId, {
        draft_content: editorContent,
      });
      await mutateChapters();
      toast.success("已儲存");
    } catch {
      toast.error("儲存失敗");
    }
  };

  const handleConvertScript = async (target: "simplified" | "traditional") => {
    if (!selectedChapterId) return;
    setConvertingScript(true);
    try {
      const updated = await api.convertChapterScript(projectId, selectedChapterId, target);
      await mutateChapters();
      // Update editor to show the converted finalized content
      setEditorContent(updated.final_content || "");
      toast.success(target === "simplified" ? "已轉為簡體中文" : "已轉為繁體中文");
    } catch {
      toast.error("轉換失敗");
    } finally {
      setConvertingScript(false);
    }
  };

  const handleRenameTitle = async (title: string) => {
    if (!selectedChapterId) return;
    try {
      await api.updateChapter(projectId, selectedChapterId, { title });
      await mutateChapters();
      toast.success("標題已更新");
    } catch {
      toast.error("標題更新失敗");
    }
  };

  const handleSaveOutline = async () => {
    try {
      await api.updateProject(projectId, { outline: outlineContent });
      await mutateProject();
      toast.success("大綱已儲存");
    } catch {
      toast.error("儲存失敗");
    }
  };

  const handleGenerateArcPlan = async () => {
    const before = JSON.stringify(project?.arc_plan ?? null);
    setGeneratingArcPlan(true);
    try {
      await api.generateArcPlan(projectId);
    } catch {
      toast.error("無法啟動藍圖生成");
      setGeneratingArcPlan(false);
      return;
    }
    const maxAttempts = 60;
    let attempts = 0;
    const poll = async (): Promise<void> => {
      attempts++;
      if (attempts > maxAttempts) {
        if (mountedRef.current) {
          setGeneratingArcPlan(false);
          toast.error("生成時間較長，請稍後重新整理");
        }
        return;
      }
      try {
        const fresh = await api.getProject(projectId);
        if (!mountedRef.current) return;
        const now = JSON.stringify(fresh.arc_plan ?? null);
        if (fresh.arc_plan && now !== before) {
          await mutateProject();
          setGeneratingArcPlan(false);
          toast.success("故事藍圖已生成");
          return;
        }
      } catch {
        // continue polling
      }
      if (mountedRef.current) setTimeout(poll, 3000);
    };
    await poll();
  };

  const handleStyleChange = async (styleId: string | null) => {
    try {
      await api.updateProject(projectId, { active_style_id: styleId });
      await mutateProject();
      setShowStyleDropdown(false);
      toast.success("風格已更新");
    } catch {
      toast.error("更新風格失敗");
    }
  };

  const handleResetPreferences = async () => {
    try {
      await api.resetWritingPreferences(projectId);
      await mutateProject();
      toast.success("寫作偏好已重設");
    } catch {
      toast.error("重設失敗");
    }
  };

  const handleUpdateStyleControls = async (controls: Record<string, number>) => {
    try {
      await api.updateProject(projectId, { style_controls: controls });
      await mutateProject();
      toast.success("風格控制已保存");
    } catch {
      toast.error("保存風格控制失敗");
    }
  };

  const handleCreateFromBranch = (branch: ForeseerBranch) => {
    setNewChapterDirection(branch.suggested_direction);
    setNewChapterTab("ai");
    setShowNewChapterModal(true);
  };

  const handleExport = async (format: "epub" | "docx") => {
    setExporting(true);
    setShowExportDropdown(false);
    try {
      const response = await api.exportProject(projectId, format);
      const blob = new Blob([response.data], { type: response.headers["content-type"] as string });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${project?.title || "小說"}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success(`已導出為 ${format.toUpperCase()}`);
    } catch (err: unknown) {
      const error = err as { response?: { data?: Blob } };
      if (error.response?.data instanceof Blob) {
        const text = await error.response.data.text();
        try {
          const json = JSON.parse(text);
          toast.error(json.detail || "導出失敗");
        } catch {
          toast.error("導出失敗");
        }
      } else {
        toast.error("導出失敗");
      }
    } finally {
      setExporting(false);
    }
  };

  // --- Loading State ---

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-500">專案不存在或無權限存取</p>
      </div>
    );
  }

  // --- Render ---

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Left Sidebar - Chapter List */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">章節列表</h2>
          <button
            onClick={() => setShowNewChapterModal(true)}
            className="p-1.5 rounded-md hover:bg-indigo-50 text-indigo-600 transition-colors"
            title="新建章節"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {chapters.length === 0 ? (
            <div className="p-4 text-center text-sm text-gray-400">
              尚無章節
            </div>
          ) : (
            chapters.map((chapter) => {
              const st = statusLabel(chapter.status);
              const isSelected = chapter.id === selectedChapterId;
              return (
                <button
                  key={chapter.id}
                  onClick={() => setSelectedChapterId(chapter.id)}
                  className={`w-full text-left px-4 py-3 border-b border-gray-100 transition-colors ${
                    isSelected
                      ? "bg-indigo-50 border-l-2 border-l-indigo-500"
                      : "hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-800">
                      第 {chapter.chapter_number} 章
                    </span>
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ${st.color}`}
                    >
                      {st.text}
                    </span>
                  </div>
                  {chapter.title && (
                    <p className="text-xs text-gray-500 mt-0.5 truncate">
                      {chapter.title}
                    </p>
                  )}
                </button>
              );
            })
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/dashboard")}
              className="p-1.5 rounded-md hover:bg-gray-100 text-gray-600 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-gray-900">
                {project.title}
              </h1>
              {project.genre && (
                <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">
                  {project.genre}
                </span>
              )}
            </div>
            {/* Style Selector */}
            <div className="relative">
              <button
                onClick={() => setShowStyleDropdown(!showStyleDropdown)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
              >
                <span className="text-gray-700">
                  {activeStyle ? activeStyle.name : "選擇風格"}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
              </button>
              {showStyleDropdown && (
                <div className="absolute top-full left-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                  <button
                    onClick={() => handleStyleChange(null)}
                    className="w-full text-left px-3 py-2 text-sm text-gray-500 hover:bg-gray-50"
                  >
                    無風格
                  </button>
                  {styles.map((style) => (
                    <button
                      key={style.id}
                      onClick={() => handleStyleChange(style.id)}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 ${
                        style.id === project.active_style_id
                          ? "text-indigo-600 font-medium"
                          : "text-gray-700"
                      }`}
                    >
                      {style.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {/* Export Button */}
            <div className="relative">
              <button
                onClick={() => setShowExportDropdown(!showExportDropdown)}
                disabled={exporting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-50 hover:bg-green-100 text-green-700 border border-green-200 rounded-md transition-colors disabled:opacity-50"
              >
                {exporting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5" />
                )}
                <span>導出</span>
                <ChevronDown className="w-3 h-3" />
              </button>
              {showExportDropdown && (
                <div className="absolute top-full right-0 mt-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                  <button
                    onClick={() => handleExport("epub")}
                    className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-t-lg"
                  >
                    📖 導出 EPUB
                  </button>
                  <button
                    onClick={() => handleExport("docx")}
                    className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-b-lg"
                  >
                    📄 導出 Word
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Tabs */}
          <div className="flex items-center gap-6">
            <nav className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {(
                [
                  { key: "editor", label: "編輯器" },
                  { key: "outline", label: "大綱" },
                  { key: "settings", label: "設定" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
                    activeTab === tab.key
                      ? "bg-white text-indigo-600 font-medium shadow-sm"
                      : "text-gray-600 hover:text-gray-800"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
            {activeStyle && (
              <span className="text-xs text-gray-500">
                風格: <span className="font-medium text-gray-700">{activeStyle.name}</span>
              </span>
            )}
          </div>
        </header>

        {/* Tab Content */}
        <main className="flex-1 overflow-y-auto">
          {activeTab === "editor" && (
            <EditorTab
              selectedChapter={selectedChapter}
              editorContent={editorContent}
              setEditorContent={setEditorContent}
              generating={generating}
              finalizing={finalizing}
              convertingScript={convertingScript}
              onGenerate={handleGenerate}
              onFinalize={handleFinalize}
              onSave={handleSaveContent}
              onRenameTitle={handleRenameTitle}
              onCreateFromBranch={handleCreateFromBranch}
              onConvertScript={handleConvertScript}
            />
          )}
          {activeTab === "outline" && (
            <OutlineTab
              outlineContent={outlineContent}
              setOutlineContent={setOutlineContent}
              onSave={handleSaveOutline}
              chapters={chapters}
              arcPlan={project?.arc_plan ?? null}
              generatingArcPlan={generatingArcPlan}
              onGenerateArcPlan={handleGenerateArcPlan}
            />
          )}
          {activeTab === "settings" && (
            <SettingsTab
              project={project}
              onResetPreferences={handleResetPreferences}
              onUpdateStyleControls={handleUpdateStyleControls}
              showCharJsonView={showCharJsonView}
              setShowCharJsonView={setShowCharJsonView}
            />
          )}
        </main>
      </div>

      {/* New Chapter Modal */}
      {showNewChapterModal && (
        <NewChapterModal
          tab={newChapterTab}
          setTab={setNewChapterTab}
          title={newChapterTitle}
          setTitle={setNewChapterTitle}
          direction={newChapterDirection}
          setDirection={setNewChapterDirection}
          content={newChapterContent}
          setContent={setNewChapterContent}
          onClose={() => {
            setShowNewChapterModal(false);
            setNewChapterDirection("");
            setNewChapterTitle("");
            setNewChapterContent("");
          }}
          onCreate={handleCreateChapter}
        />
      )}

      {/* Click outside style dropdown */}
      {showStyleDropdown && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowStyleDropdown(false)}
        />
      )}
    </div>
  );
}
