"use client";

import type { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Tailwind max-width class, e.g. "max-w-md". Defaults to "max-w-md". */
  maxWidth?: string;
}

/**
 * Shared modal overlay. Replaces the per-page inline modal markup
 * (dashboard / styles / new-chapter) with a single consistent implementation.
 */
export function Modal({ open, onClose, title, children, maxWidth = "max-w-md" }: ModalProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
      <div className={`bg-white rounded-xl w-full ${maxWidth} p-6 shadow-xl`}>
        <h3 className="text-xl font-bold text-gray-900 mb-5">{title}</h3>
        {children}
      </div>
    </div>
  );
}
