import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, STIX_Two_Text } from "next/font/google";
import "./globals.css";

// Type roles (design tokens): STIX Two Text carries the educator questions
// (display only — numbers and chart text always stay in the sans);
// IBM Plex Sans is the working face; Plex Mono is reserved for data identifiers.
const displaySerif = STIX_Two_Text({
  variable: "--font-display",
  subsets: ["latin"],
});

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "StatsBot Educator Dashboard",
  description: "Aggregated, privacy-floored StatsBot usage insights for educators",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${displaySerif.variable} ${plexSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-paper text-ink font-sans">{children}</body>
    </html>
  );
}
