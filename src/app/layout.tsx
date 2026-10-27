import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NoteWise — AI-конспекты уроков",
  description: "Локальные записи и AI-конспекты ваших занятий.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
