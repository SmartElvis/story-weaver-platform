import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import { SWRProvider } from "@/components/SWRProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 小說創作平台",
  description: "AI-powered novel writing platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" data-color-mode="light">
      <body className="antialiased">
        <SWRProvider>
          <Toaster position="top-right" />
          {children}
        </SWRProvider>
      </body>
    </html>
  );
}
