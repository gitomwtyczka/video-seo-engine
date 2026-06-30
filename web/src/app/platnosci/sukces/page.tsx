"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function PlatnosCiSukces() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Animate in after mount
    const t = setTimeout(() => setShow(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 flex items-center justify-center px-4">
      <div
        className={`max-w-md w-full text-center transition-all duration-700 ${
          show ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
        }`}
      >
        {/* Success icon */}
        <div className="mx-auto mb-8 w-24 h-24 rounded-full bg-green-900/30 border border-green-500/40 flex items-center justify-center shadow-[0_0_40px_rgba(34,197,94,0.15)]">
          <svg
            className="w-12 h-12 text-green-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>

        <h1 className="text-3xl font-extrabold text-white mb-3">
          Płatność potwierdzona!
        </h1>
        <p className="text-gray-400 mb-2">
          Dziękujemy za subskrypcję. Twój plan zostanie aktywowany w ciągu kilku
          sekund.
        </p>
        <p className="text-gray-500 text-sm mb-10">
          Otrzymasz potwierdzenie na adres email powiązany z kontem.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            id="btn-go-dashboard"
            href="/dashboard"
            className="px-6 py-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-sm transition-colors shadow-lg shadow-violet-900/40"
          >
            Przejdź do dashboardu
          </Link>
          <Link
            id="btn-go-home"
            href="/"
            className="px-6 py-3 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold text-sm transition-colors border border-gray-700/50"
          >
            Strona główna
          </Link>
        </div>
      </div>
    </main>
  );
}
