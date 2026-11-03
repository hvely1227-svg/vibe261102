import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { PenSquare } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "DemoWeb 게시판",
    template: "%s | DemoWeb 게시판",
  },
  description: "Next.js와 shadcn/ui로 만든 간단한 게시판",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ko"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-muted/40">
        <header className="border-b bg-background">
          <div className="mx-auto flex h-14 w-full max-w-4xl items-center justify-between px-4">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              DemoWeb 게시판
            </Link>
            <Link href="/posts/new" className={buttonVariants()}>
              <PenSquare />
              글쓰기
            </Link>
          </div>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t bg-background py-4 text-center text-xs text-muted-foreground">
          © DemoWeb
        </footer>
      </body>
    </html>
  );
}
