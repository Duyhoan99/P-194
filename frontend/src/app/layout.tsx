import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { LanguageProvider } from "@/lib/i18n";

import { Inter, Newsreader } from "next/font/google";
import { RootLayoutWrapper } from "@/components/RootLayoutWrapper";

const inter = Inter({ 
  subsets: ["latin", "vietnamese"],
  display: "swap",
  variable: "--font-inter",
});

const serifFont = Newsreader({
  subsets: ["latin", "vietnamese"],
  display: "swap",
  style: ["normal", "italic"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-serif",
});

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
    <html lang="vi" className={`${inter.variable} ${serifFont.variable}`}>
      <body className={`${inter.className} bg-slate-100 dark:bg-[#0b1528] text-slate-900 dark:text-slate-200 antialiased font-sans transition-colors duration-300`}>
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

