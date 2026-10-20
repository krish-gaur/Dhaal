import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppHeader } from "@/components/AppHeader";
import { LangProvider } from "@/lib/useLang";
import "./globals.css";

export const metadata: Metadata = {
  title: "DHAAL — what will you actually pay?",
  description:
    "Evidence-linked estimates of out-of-pocket hospital costs for insured Indian households. Every rupee traced to a policy clause.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LangProvider>
          <AppHeader />
          <main>{children}</main>
        </LangProvider>
      </body>
    </html>
  );
}
