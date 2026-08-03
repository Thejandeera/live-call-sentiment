import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Live Call Sentiment",
  description: "Real-time live call monitoring and supervisor alertness system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
