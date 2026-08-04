import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Clinical Summary Agent — AI20K",
  description: "Hệ thống AI hỗ trợ tóm tắt hồ sơ lâm sàng cho bác sĩ, xây dựng trên MIMIC-IV",
  keywords: "clinical, AI, MIMIC-IV, medical, summary, healthcare",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
