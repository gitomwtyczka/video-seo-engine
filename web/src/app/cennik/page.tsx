"use client";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://vse.impresjapr.pl";

const plans = [
  {
    id: "starter",
    name: "Starter",
    price: "49",
    description: "Dla twórców i małych portali",
    features: [
      "30 filmów / miesiąc",
      "3 portale WordPress",
      "VideoObject Schema",
      "Chapters + FAQ AI",
      "Cross-Language: wideo z dowolnego języka → SEO w języku panelu",
      "Opcjonalny Add-on: Pakiet Wielojęzyczny (+29 zł/mies.)",
      "Pakiet VSE Desktop Runner (.zip)",
      "Dostęp do API",
      "Email support",
    ],
    highlight: false,
  },
  {
    id: "pro",
    name: "Pro",
    price: "149",
    description: "Dla profesjonalnych twórców treści",
    features: [
      "150 filmów / miesiąc",
      "10 portali WordPress",
      "🌐 Pakiet Wielojęzyczny (8 języków) W CENIE",
      "Tłumaczenie poszczególnych zakładek 1 kliknięciem",
      "Pakiet VSE Desktop Runner (.zip)",
      "Pakiet analiz Premium AI",
      "VideoObject Schema",
      "Chapters + FAQ AI",
      "Dostęp do API",
      "Priorytetowy support",
      "Monitor kanału YouTube",
    ],
    highlight: true,
  },
  {
    id: "agency",
    name: "Agency",
    price: "499",
    description: "Dla agencji i dużych wydawców",
    features: [
      "500 filmów / miesiąc",
      "50 portali WordPress",
      "🌐 Pełny Multi-Language (8 języków) bez limitu adaptacji",
      "Pakiet VSE Desktop Runner (.zip)",
      "Priorytetowe AI & wsparcie",
      "VideoObject Schema",
      "Chapters + FAQ AI",
      "Dostęp do API",
      "Dedykowany support",
      "Monitor kanału YouTube",
      "White-label API",
    ],
    highlight: false,
  },
];

export default function CennikPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubscribe = async (planId: string) => {
    if (!session) {
      router.push("/login?redirect=/cennik");
      return;
    }
    setLoading(planId);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/v1/payments/create-checkout-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${(session as { accessToken?: string }).accessToken || ""}`,
        },
        body: JSON.stringify({ plan_id: planId }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Błąd podczas tworzenia sesji płatności");
      }
      const { session_url } = await res.json();
      window.location.href = session_url;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Nieznany błąd");
      setLoading(null);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 py-20 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <span className="inline-block px-4 py-1 rounded-full text-xs font-semibold bg-violet-900/40 text-violet-300 border border-violet-700/40 mb-4 uppercase tracking-widest">
            Cennik
          </span>
          <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-4">
            Wybierz swój plan
          </h1>
          <p className="text-gray-400 text-lg max-w-xl mx-auto">
            Automatyzuj SEO wideo. Płać miesięcznie, anuluj kiedy chcesz.
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-8 p-4 bg-red-900/30 border border-red-700/50 rounded-xl text-red-300 text-sm text-center">
            {error}
          </div>
        )}

        {/* Plans grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`relative rounded-2xl border p-8 flex flex-col transition-all duration-300 ${
                plan.highlight
                  ? "bg-violet-900/30 border-violet-500/60 shadow-[0_0_40px_rgba(139,92,246,0.15)] scale-105"
                  : "bg-gray-900/60 border-gray-700/50 hover:border-gray-600/70"
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="px-4 py-1 rounded-full text-xs font-bold bg-violet-600 text-white uppercase tracking-wider shadow-lg">
                    Najpopularniejszy
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h2 className="text-xl font-bold text-white mb-1">{plan.name}</h2>
                <p className="text-gray-400 text-sm">{plan.description}</p>
              </div>

              <div className="mb-8">
                <span className="text-5xl font-extrabold text-white">{plan.price}</span>
                <span className="text-gray-400 ml-2">zł / mies.</span>
              </div>

              <ul className="space-y-3 mb-8 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-3 text-sm text-gray-300">
                    <svg className="w-4 h-4 text-violet-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>

              <button
                id={`btn-subscribe-${plan.id}`}
                onClick={() => handleSubscribe(plan.id)}
                disabled={loading !== null}
                className={`w-full py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${
                  plan.highlight
                    ? "bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-900/50"
                    : "bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700/50"
                } disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {loading === plan.id ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    Przekierowanie...
                  </span>
                ) : (
                  "Wybierz plan"
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Dedicated Add-on: Pakiet Wielojęzyczny */}
        <div className="mt-12 rounded-2xl border border-indigo-500/40 bg-gradient-to-r from-indigo-950/60 via-violet-950/50 to-gray-900/70 p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 shadow-[0_0_30px_rgba(99,102,241,0.12)]">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-3 py-0.5 rounded-full text-xs font-bold bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 uppercase tracking-wider">
                Opcjonalny Add-on do planu Starter
              </span>
              <span className="text-xs text-emerald-400 font-semibold">
                ✨ W planach Pro i Agency w cenie!
              </span>
            </div>
            <h3 className="text-xl md:text-2xl font-bold text-white">
              🌐 Add-on: Pakiet Wielojęzyczny — +29 zł / mies.
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              Generuj artykuły, streszczenia, posty Social Media i pełne Schema.org w <strong className="text-white">8 językach</strong> (🇵🇱 PL, 🇬🇧 EN, 🇩🇪 DE, 🇪🇸 ES, 🇫🇷 FR, 🇮🇹 IT, 🇺🇦 UK, 🇵🇹 PT) z dowolnego wideo. Tłumacz wybrane zakładki 1 kliknięciem bez ponownego pobierania filmu i bez zużywania limitu wideo.
            </p>
          </div>
          <div className="flex flex-col items-stretch sm:items-end gap-2.5 w-full md:w-auto flex-shrink-0">
            <button
              id="btn-subscribe-starter-multilang"
              onClick={() => handleSubscribe("starter_multilang")}
              disabled={loading !== null}
              className="px-6 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-indigo-900/50 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading === "starter_multilang" ? "Przekierowanie..." : "🚀 Kup Starter + 8 Języków (78 zł/mies.)"}
            </button>
            <button
              id="btn-subscribe-multilang-addon"
              onClick={() => handleSubscribe("multilang_addon")}
              disabled={loading !== null}
              className="px-5 py-2.5 rounded-xl font-semibold text-xs bg-gray-800/90 hover:bg-gray-700 text-indigo-200 border border-indigo-500/40 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading === "multilang_addon" ? "Przekierowanie..." : "Mam już Starter — dokup Add-on (+29 zł/mies.)"}
            </button>
            <span className="text-xs text-gray-400 text-center sm:text-right">
              Aktywacja natychmiast po płatności Stripe
            </span>
          </div>
        </div>

        {/* Free tier note */}
        <p className="text-center text-gray-500 text-sm mt-12">
          Używasz planu <span className="text-gray-300 font-medium">Free</span>? Masz 5 filmów/mies. za darmo.{" "}
          <a href="/dashboard" className="text-violet-400 hover:text-violet-300 underline">
            Wróć do dashboardu
          </a>
        </p>
      </div>
    </main>
  );
}
