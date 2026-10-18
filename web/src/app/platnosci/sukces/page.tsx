"use client";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export default function PlatnosCiSukces() {
  const { data: session, update } = useSession();
  const [show, setShow] = useState(false);
  const [verifiedPlan, setVerifiedPlan] = useState<string | null>(null);
  const verifiedRef = useRef(false);

  useEffect(() => {
    const t = setTimeout(() => setShow(true), 100);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (verifiedRef.current) return;
    const accessToken = (session as { accessToken?: string } | null)?.accessToken;
    if (!accessToken) return;
    verifiedRef.current = true;

    const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    const sessionId = params?.get("session_id") || undefined;

    fetch(`${API_URL}/v1/payments/verify-session`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then(async (data) => {
        if (data?.plan_id) {
          setVerifiedPlan(
            data.plan_id === "starter" && data.has_multilang_addon
              ? "Starter + 🌐 Pakiet 8 Języków"
              : data.plan_id.toUpperCase()
          );
        }
        try {
          await update();
        } catch {
          // ignore
        }
      })
      .catch(() => {});
  }, [session, update]);

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
          Dziękujemy za subskrypcję.{" "}
          {verifiedPlan ? (
            <span className="text-emerald-400 font-semibold">
              Aktywowano plan: {verifiedPlan}.
            </span>
          ) : (
            "Twój plan został aktywowany na koncie."
          )}
        </p>
        <p className="text-gray-500 text-sm mb-10">
          Otrzymasz potwierdzenie na adres email powiązany z kontem.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            id="btn-go-dashboard"
            href="/dashboard?upgraded=1"
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
