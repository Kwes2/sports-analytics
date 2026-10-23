import "./globals.css";
import React from "react";

export const metadata = {
  title: "CourtIQ | Advanced NBA Analytics Hub",
  description: "Custom metrics, live player evaluation and advanced statistics.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased selection:bg-blue-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}