import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Line Relay - AI台词接龙视频生成器",
  description: "输入一句台词，AI自动生成搞笑台词接龙视频",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <body className="min-h-screen bg-background antialiased">{children}</body>
    </html>
  );
}
