"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import toast from "react-hot-toast";
import { Plus, Trash2, Settings, LogOut, BookOpen, Palette } from "lucide-react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { useAuth } from "@/lib/useAuth";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

const GENRES = ["都市", "歷史", "武俠", "科幻", "奇幻", "懸疑", "言情"];

const GENRE_COLORS: Record<string, string> = {
  都市: "bg-blue-100 text-blue-700",
  歷史: "bg-amber-100 text-amber-700",
  武俠: "bg-red-100 text-red-700",
  科幻: "bg-purple-100 text-purple-700",
  奇幻: "bg-emerald-100 text-emerald-700",
  懸疑: "bg-gray-100 text-gray-700",
  言情: "bg-pink-100 text-pink-700",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  in_progress: "進行中",
  completed: "已完成",
};

interface Project {
  id: string;
  title: string;
  genre: string | null;
  description: string | null;
  status?: string;
  chapter_count?: number;
  created_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, logout } = useStore();
  const { token, ready } = useAuth();
  const {
    data: projects = [],
    isLoading: loading,
    mutate: mutateProjects,
  } = useSWR<Project[]>(
    ready && token ? "projects" : null,
    () => api.listProjects(),
    { onError: () => toast.error("載入專案失敗") }
  );
  const [showModal, setShowModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newGenre, setNewGenre] = useState(GENRES[0]);
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      toast.error("請輸入作品名稱");
      return;
    }
    setCreating(true);
    try {
      await api.createProject({
        title: newTitle,
        genre: newGenre,
        description: newDescription,
      });
      toast.success("專案建立成功");
      setShowModal(false);
      setNewTitle("");
      setNewGenre(GENRES[0]);
      setNewDescription("");
      mutateProjects();
    } catch {
      toast.error("建立專案失敗");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProject = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("確定要刪除此專案嗎？")) return;
    try {
      await api.deleteProject(id);
      toast.success("專案已刪除");
      mutateProjects(projects.filter((p) => p.id !== id), { revalidate: false });
    } catch {
      toast.error("刪除失敗");
    }
  };

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-indigo-600" />
            <h1 className="text-lg font-bold text-gray-900">AI 小說創作平台</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">{user?.username}</span>
            <button
              onClick={() => router.push("/styles")}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              title="風格管理"
            >
              <Palette className="w-5 h-5" />
            </button>
            <button
              onClick={() => router.push("/settings")}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              title="設定"
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              onClick={handleLogout}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              title="登出"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">我的作品</h2>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            新建專案
          </button>
        </div>

        {loading ? (
          <div className="text-center py-20 text-gray-500">載入中...</div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20">
            <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">尚無作品，點擊「新建專案」開始創作</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => router.push(`/projects/${project.id}`)}
                className="bg-white border border-gray-200 rounded-xl p-5 cursor-pointer hover:shadow-md hover:border-indigo-200 transition-all group relative"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-semibold text-gray-900 text-lg truncate pr-8">
                    {project.title}
                  </h3>
                  <button
                    onClick={(e) => handleDeleteProject(project.id, e)}
                    className="absolute top-4 right-4 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                    title="刪除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex items-center gap-2 mb-3">
                  {project.genre && (
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        GENRE_COLORS[project.genre] || "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {project.genre}
                    </span>
                  )}
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600">
                    {STATUS_LABELS[project.status || "draft"] || project.status || "草稿"}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm text-gray-500">
                  <span>{project.chapter_count ?? 0} 章</span>
                  <span>{new Date(project.created_at).toLocaleDateString("zh-TW")}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* New Project Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="新建專案">
        <form onSubmit={handleCreateProject} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              作品名稱
            </label>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
              placeholder="輸入作品名稱"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              類型
            </label>
            <select
              value={newGenre}
              onChange={(e) => setNewGenre(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 bg-white"
            >
              {GENRES.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              簡介
            </label>
            <textarea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 resize-none"
              rows={3}
              placeholder="簡短描述您的作品"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
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
