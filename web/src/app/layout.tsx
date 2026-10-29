import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Portal Oleofinos", template: "%s · Portal Oleofinos" },
  description: "Portal interno de Oleofinos.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es-MX" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
