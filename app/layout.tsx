import "./globals.css";
import React from "react";
import Navbar from "../components/Navbar";

export const metadata = {
  title: "CourtIQ | Advanced NBA Intelligence",
  description: "Next-generation sports analytics and custom metric modeling.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased selection:bg-zinc-800 selection:text-white">
        <Navbar />
        {children}
      </body>
    </html>
  );
}