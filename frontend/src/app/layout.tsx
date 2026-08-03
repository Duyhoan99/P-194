import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Clinical Doctor Review Demo",
  description: "Synthetic-data doctor review workflow.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
