"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import toast from "react-hot-toast";
import { ArrowLeft, Plus, Trash2, Upload, FileText, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

interface StyleProfile {
  id: string;
  name: string;
  author_name: string | null;
  description: string | null;
  total_chunks: number;
  source_books: { name: string }[] | null;
  style_features: Record<string, unknown> | null;
  processing_status: string | null;
}

interface UploadedWork {
  name: string;
}

export default function StylesPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const mountedRef = useRef(true);
  const {
    data: styles = [],
    isLoading: loading,
    mutate: mutateStyles,
  } = useSWR<StyleProfile[]>(
    ready && token ? "styles" : null,
    () => api.listStyles(),
    { onError: () => toast.error("載入風格列表失敗") }
  );
  const [selectedStyle, setSelectedStyle] = useState<StyleProfile | null>(null);
  const [works, setWorks] = useState<UploadedWork[]>([]);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAuthor, setNewAuthor] = useState("");
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Auto-select the first style once the list loads and nothing is selected.
  useEffect(() => {
    if (styles.length > 0 && !selectedStyle) {
      selectStyle(styles[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [styles]);

  const selectStyle = async (style: StyleProfile) => {
    setSelectedStyle(style);
    try {
      const fullStyle = await api.getStyle(style.id);
      setSelectedStyle(fullStyle);
      setWorks(fullStyle.source_books || []);
    } catch {
      setWorks([]);
    }
  };

  const handleCreateStyle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) {
      toast.error("請輸入風格名稱");
      return;
    }
    setCreating(true);
    try {
      const created = await api.createStyle({ name: newName, author_name: newAuthor });
      toast.success("風格建立成功");
      setShowNewModal(false);
      setNewName("");
      setNewAuthor("");
      mutateStyles([...styles, created], { revalidate: false });
      selectStyle(created);
    } catch {
      toast.error("建立失敗");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteStyle = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("確定要刪除此風格嗎？")) return;
    try {
      await api.deleteStyle(id);
      toast.success("風格已刪除");
      const updated = styles.filter((s) => s.id !== id);
      mutateStyles(updated, { revalidate: false });
      if (selectedStyle?.id === id) {
        if (updated.length > 0) {
          selectStyle(updated[0]);
        } else {
          setSelectedStyle(null);
          setWorks([]);
        }
      }
    } catch {
      toast.error("刪除失敗");
    }
  };

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0 || !selectedStyle) return;
    const file = files[0];
    const validTypes = [".epub", ".txt", ".pdf"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!validTypes.includes(ext)) {
      toast.error("僅支援 .epub, .txt, .pdf 格式");
      return;
    }
    setUploading(true);
    try {
      await api.uploadStyleFiles(selectedStyle.id, [file]);
      toast.success("上傳成功，背景處理中...");
      // Refresh style to get updated data
      const updatedStyle = await api.getStyle(selectedStyle.id);
      setSelectedStyle(updatedStyle);
      setWorks(updatedStyle.source_books || []);
      mutateStyles(
        styles.map((s) => (s.id === updatedStyle.id ? updatedStyle : s)),
        { revalidate: false }
      );
      // Poll for processing completion
      const pollChunks = async () => {
        for (let i = 0; i < 30; i++) {
          await new Promise((r) => setTimeout(r, 3000));
          if (!mountedRef.current) return;
          const s = await api.getStyle(selectedStyle.id);
          if (!mountedRef.current) return;
          setSelectedStyle(s);
          mutateStyles((prev) => (prev || []).map((x) => (x.id === s.id ? s : x)), {
            revalidate: false,
          });
          if (s.processing_status === "ready" || s.processing_status === "failed") {
            if (s.processing_status === "ready") {
              toast.success("文件處理完成，可以啟動分析");
            } else {
              toast.error("文件處理失敗，請重新上傳");
            }
            return;
          }
        }
        if (mountedRef.current) toast.error("處理超時，請稍後刷新頁面");
      };
      pollChunks();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "上傳失敗";
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFileUpload(e.dataTransfer.files);
  };

  const handleAnalyze = async () => {
    if (!selectedStyle) return;
    setAnalyzing(true);
    // Snapshot the current features so we can tell a *new* result apart from a
    // stale one: re-analyzing a style that already has features would otherwise
    // make the poll below return immediately with the old data (false positive).
    const before = JSON.stringify(selectedStyle.style_features ?? null);
    try {
      await api.analyzeStyle(selectedStyle.id);
      toast.success("風格分析已啟動，背景處理中...");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "分析失敗";
      toast.error(msg);
      setAnalyzing(false);
      return;
    }
    // Poll for results since analysis runs in background. Profiling is a
    // map-reduce over many LLM batches and can take several minutes, so poll
    // for up to ~10 minutes. The old 90-second window always gave up early,
    // which made the button appear unresponsive.
    const poll = async () => {
      for (let i = 0; i < 200; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        if (!mountedRef.current) return;
        try {
          const updated = await api.getStyle(selectedStyle.id);
          if (!mountedRef.current) return;
          const now = JSON.stringify(updated.style_features ?? null);
          if (updated.style_features && now !== before) {
            setSelectedStyle(updated);
            mutateStyles((prev) => (prev || []).map((s) => (s.id === updated.id ? updated : s)), {
              revalidate: false,
            });
            toast.success("風格分析完成");
            setAnalyzing(false);
            return;
          }
        } catch {
          // transient polling error; keep trying
        }
      }
      if (mountedRef.current) {
        toast.error("分析時間較長，請稍後刷新頁面查看結果");
        setAnalyzing(false);
      }
    };
    poll();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">載入中...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/dashboard")}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-bold text-gray-900">風格管理</h1>
          </div>
          <button
            onClick={() => setShowNewModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            新建風格
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-6 min-h-[calc(100vh-10rem)]">
          {/* Left Panel - Style List */}
          <div className="w-80 flex-shrink-0">
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              {styles.length === 0 ? (
                <div className="p-6 text-center text-gray-500 text-sm">
                  尚無風格，點擊「新建風格」開始
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {styles.map((style) => (
                    <div
                      key={style.id}
                      onClick={() => selectStyle(style)}
                      className={`px-4 py-3.5 cursor-pointer hover:bg-gray-50 transition-colors group relative ${
                        selectedStyle?.id === style.id
                          ? "bg-indigo-50 border-l-2 border-indigo-600"
                          : ""
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-gray-900 truncate">
                            {style.name}
                          </h4>
                          <p className="text-sm text-gray-500 mt-0.5">
                            {style.author_name || "未指定作者"}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className="text-xs text-gray-400">
                              {style.total_chunks} 篇
                            </span>
                            {style.processing_status === "processing" && (
                              <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                                處理中
                              </span>
                            )}
                            {style.style_features && (
                              <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-green-100 text-green-700">
                                已分析
                              </span>
                            )}
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteStyle(style.id, e)}
                          className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                          title="刪除"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Style Detail */}
          <div className="flex-1">
            {selectedStyle ? (
              <div className="space-y-6">
                {/* Upload Area */}
                <div className="bg-white border border-gray-200 rounded-xl p-6">
                  <h3 className="font-semibold text-gray-900 mb-4">上傳作品</h3>
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragOver(true);
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                      dragOver
                        ? "border-indigo-400 bg-indigo-50"
                        : "border-gray-300 hover:border-indigo-300 hover:bg-gray-50"
                    }`}
                  >
                    <Upload className="w-8 h-8 text-gray-400 mx-auto mb-3" />
                    <p className="text-sm text-gray-600 mb-1">
                      拖拽檔案到此處，或點擊選擇檔案
                    </p>
                    <p className="text-xs text-gray-400">支援 .epub, .txt, .pdf</p>
                    {uploading && (
                      <p className="text-sm text-indigo-600 mt-2">上傳中...</p>
                    )}
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".epub,.txt,.pdf"
                    className="hidden"
                    onChange={(e) => handleFileUpload(e.target.files)}
                  />
                </div>

                {/* Uploaded Works */}
                <div className="bg-white border border-gray-200 rounded-xl p-6">
                  <h3 className="font-semibold text-gray-900 mb-4">已上傳作品</h3>
                  {works.length === 0 ? (
                    <p className="text-sm text-gray-500">尚無上傳作品</p>
                  ) : (
                    <div className="space-y-2">
                      {works.map((work, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-3 px-3 py-2 bg-gray-50 rounded-lg"
                        >
                          <FileText className="w-4 h-4 text-gray-400" />
                          <span className="text-sm text-gray-700 flex-1 truncate">
                            {work.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Analyze Button */}
                <div className="bg-white border border-gray-200 rounded-xl p-6">
                  {selectedStyle.processing_status === "processing" && (
                    <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
                      <div className="w-3 h-3 rounded-full bg-amber-400 animate-pulse" />
                      <span className="text-sm text-amber-700">文件處理中，請稍候...</span>
                    </div>
                  )}
                  {selectedStyle.processing_status === "failed" && (
                    <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
                      <span className="text-sm text-red-700">文件處理失敗，請重新上傳</span>
                    </div>
                  )}
                  <button
                    onClick={handleAnalyze}
                    disabled={analyzing || works.length === 0 || selectedStyle.processing_status === "processing"}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Sparkles className="w-4 h-4" />
                    {analyzing ? "分析中..." : "啟動風格分析 (The Profiler)"}
                  </button>
                  {works.length === 0 && (
                    <p className="text-xs text-gray-400 mt-2">請先上傳至少一部作品</p>
                  )}
                </div>

                {/* Analysis Result */}
                {selectedStyle.style_features && (
                  <div className="bg-white border border-gray-200 rounded-xl p-6">
                    <h3 className="font-semibold text-gray-900 mb-4">風格特徵面板</h3>
                    <pre className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700 overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(selectedStyle.style_features, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl p-12 text-center">
                <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">選擇或建立一個風格開始</p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* New Style Modal */}
      <Modal open={showNewModal} onClose={() => setShowNewModal(false)} title="新建風格">
        <form onSubmit={handleCreateStyle} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              風格名稱
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
              placeholder="e.g., 金庸風格"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              代表作者
            </label>
            <input
              type="text"
              value={newAuthor}
              onChange={(e) => setNewAuthor(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
              placeholder="e.g., 金庸"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={() => setShowNewModal(false)}>
              取消
            </Button>
            <Button type="submit" disabled={creating}>
              {creating ? "建立中..." : "建立"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
