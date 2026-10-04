"use client";

import Link from "next/link";
import { BookOpen, Sparkles, Users, Palette } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-white to-gray-50 px-4">
      <div className="text-center max-w-2xl">
        <div className="flex items-center justify-center mb-6">
          <BookOpen className="w-12 h-12 text-indigo-600" />
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          AI 小說創作平台
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          結合多個 AI Agent 協作，幫助您創作高品質的小說作品。從情節編織、邏輯審查到風格校正，讓 AI 成為您最強大的寫作夥伴。
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
            <Sparkles className="w-8 h-8 text-indigo-500 mx-auto mb-3" />
            <h3 className="font-semibold text-gray-800 mb-1">AI 智能創作</h3>
            <p className="text-sm text-gray-500">多 Agent 協作生成章節草稿</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
            <Users className="w-8 h-8 text-indigo-500 mx-auto mb-3" />
            <h3 className="font-semibold text-gray-800 mb-1">角色管理</h3>
            <p className="text-sm text-gray-500">自動提取與追蹤角色關係</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
            <Palette className="w-8 h-8 text-indigo-500 mx-auto mb-3" />
            <h3 className="font-semibold text-gray-800 mb-1">風格定制</h3>
            <p className="text-sm text-gray-500">分析並模仿喜愛的寫作風格</p>
          </div>
        </div>

        <div className="flex items-center justify-center gap-4">
          <Link
            href="/login"
            className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            登入
          </Link>
          <Link
            href="/register"
            className="px-6 py-3 bg-white text-indigo-600 font-medium rounded-lg border border-indigo-200 hover:bg-indigo-50 transition-colors"
          >
            註冊
          </Link>
        </div>
      </div>
    </div>
  );
}
