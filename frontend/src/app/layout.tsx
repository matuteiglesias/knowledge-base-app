import type { Metadata } from "next";
import { QueryProvider } from "../providers/query_provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Paper Corpus Workbench",
  description: "Navigate a governed Paper KB corpus through modular research tabs.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-950 antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
