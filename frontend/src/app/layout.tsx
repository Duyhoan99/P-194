import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { LanguageProvider } from "@/lib/i18n";

import { Plus_Jakarta_Sans } from "next/font/google";
import { RootLayoutWrapper } from "@/components/RootLayoutWrapper";

const mainFont = Plus_Jakarta_Sans({ subsets: ["latin", "vietnamese"] });

export const metadata: Metadata = {
  title: "Clinical Review Copilot — AI Rà Soát Bệnh Án Dọc (P-194)",
  description: "Hệ thống AI hỗ trợ tóm tắt hồ sơ lâm sàng đa nguồn & rà soát bệnh án dọc (FHIR R4 & PDF/OCR Ingestion)",
  keywords: "clinical copilot, FHIR R4, PDF OCR, longitudinal patient summary, HITL, AI20K, P-194",
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

