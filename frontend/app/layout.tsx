import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "WorkflowGPT / CI-CD Copilot",
  description: "Agentic RAG copilot for n8n workflows, GitHub Actions CI/CD, and API/HTTP error debugging.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
            <Link href="/" className="font-semibold text-ink">
              WorkflowGPT <span className="text-slate-400 font-normal">/ CI-CD Copilot</span>
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/" className="text-slate-600 hover:text-accent">
                Chat
              </Link>
              <Link href="/eval" className="text-slate-600 hover:text-accent">
                Eval Dashboard
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
