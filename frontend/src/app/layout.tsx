import type { Metadata } from "next";
import { Cinzel, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/components/Providers";

const cinzel = Cinzel({
  subsets: ["latin"],
  variable: "--font-cinzel",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MovieAI Producer | DaVinci Obsidian AI Studio",
  description: "Autonomous Hollywood AI Film Production Studio Suite",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${cinzel.variable} ${jetbrainsMono.variable} font-sans bg-canvas text-obsidian-primary antialiased min-h-screen selection:bg-amber-500/20 selection:text-amber-400`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
