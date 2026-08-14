import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { LanguageProvider } from "@/lib/i18n";

import { Plus_Jakarta_Sans } from "next/font/google";
import { RootLayoutWrapper } from "@/components/RootLayoutWrapper";

const mainFont = Plus_Jakarta_Sans({ subsets: ["latin", "vietnamese"] });

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
      <body className={`${mainFont.className} bg-slate-950 text-slate-200 antialiased`}>
        <AuthProvider>
          <LanguageProvider>
            <RootLayoutWrapper>
              {children}
            </RootLayoutWrapper>
          </LanguageProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

