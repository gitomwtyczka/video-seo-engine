"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function PlatnosCiAnulowano() {
  const [show, setShow] = useState(false);

  useEffect(() => {
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
        {/* Cancel icon */}
        <div className="mx-auto mb-8 w-24 h-24 rounded-full bg-gray-800/60 border border-gray-600/40 flex items-center justify-center">
          <svg
            className="w-12 h-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>

        <h1 className="text-3xl font-extrabold text-white mb-3">
          Płatność anulowana
        </h1>
        <p className="text-gray-400 mb-2">
          Nie pobraliśmy żadnych środków. Możesz spróbować ponownie w dowolnym
          momencie.
        </p>
        <p className="text-gray-500 text-sm mb-10">
          Nadal korzystasz z bezpłatnego planu Free (5 filmów / miesiąc).
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            id="btn-back-to-pricing"
            href="/cennik"
            className="px-6 py-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-sm transition-colors shadow-lg shadow-violet-900/40"
          >
            Powrót do cennika
          </Link>
          <Link
            id="btn-back-dashboard"
            href="/dashboard"
            className="px-6 py-3 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold text-sm transition-colors border border-gray-700/50"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
