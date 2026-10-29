import React, { useEffect, useState } from "react";
import { session } from "./api.js";
import SignIn from "./components/SignIn.jsx";
import ProfilePanel from "./components/ProfilePanel.jsx";
import Filters from "./components/Filters.jsx";
import Recommendations from "./components/Recommendations.jsx";
import CompareModels from "./components/CompareModels.jsx";
import EvaluationPanel from "./components/EvaluationPanel.jsx";
import { Segmented } from "./components/ui.jsx";
import AskAssistant from "./components/askAssistant.jsx";

const TABS = [
  { value: "recs", label: "Recommendations" },
  { value: "compare", label: "Compare models" },
  { value: "eval", label: "Evaluation" },
  { value: "ask", label: "Ask" },
];

export default function App() {
  const [userId, setUserId] = useState(() => session.get()?.userId ?? null);
  const [tab, setTab] = useState("recs");
  const [domain, setDomain] = useState("all");
  const [model, setModel] = useState("similar_shoppers");
  const [filters, setFilters] = useState({ category: "", occasion: "", colour_family: "", max_price: "", size_filter: true });
  const [profileKey, setProfileKey] = useState(0);

  // The API client fires this when the server says the token is missing, expired or invalid.
  useEffect(() => {
    const out = () => setUserId(null);
    window.addEventListener("sb-signed-out", out);
    return () => window.removeEventListener("sb-signed-out", out);
  }, []);

  const signOut = () => { session.clear(); setUserId(null); };
  if (!userId) return <SignIn onSignedIn={(id) => { setUserId(id); setTab("recs"); }} />;

  return (
    // On large screens the page itself never scrolls: the left and right panes each have their own scrollbar.
    <div className="flex min-h-screen flex-col lg:h-screen lg:overflow-hidden">
      <header className="shrink-0 border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div>
            <h1 className="text-xl font-bold tracking-tight">StyleBridge AI</h1>
            <p className="text-sm text-slate2">Clothing and accessories picked from what shoppers like you bought</p>
          </div>
          <Segmented label="View" value={tab} onChange={setTab} options={TABS} />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-4 sm:px-6 lg:min-h-0 lg:flex-row">
        {tab !== "eval" && tab !== "ask" &&(
          <aside aria-label="Your profile and search" className="w-full space-y-6 lg:w-[320px] lg:shrink-0 lg:overflow-y-auto lg:overscroll-contain lg:pb-6 lg:pr-2">
            <ProfilePanel refreshKey={`${userId}-${profileKey}`} onSwitched={(id) => setUserId(id)} onSignOut={signOut} />
            <Filters domain={domain} onDomain={setDomain} model={model} onModel={setModel} filters={filters} onFilters={setFilters} showModel={tab === "recs"} />
          </aside>
        )}
        <div className="min-w-0 flex-1 lg:overflow-auto lg:overscroll-contain lg:pb-6 lg:pr-1">
          {tab === "eval" ? <EvaluationPanel /> :
            tab === "ask" ? <AskAssistant key={userId} /> :
            tab === "recs" ? <Recommendations key={userId} domain={domain} model={model} filters={filters} onPurchase={() => setProfileKey((n) => n + 1)} /> :
            <CompareModels key={userId} filters={filters} />}
          <footer className="mt-10 text-xs text-slate2">
            All shoppers, products and interactions are synthetic. Product photos are illustrative stock images from{" "}
            <a className="underline" href="https://unsplash.com/?utm_source=stylebridge_ai&utm_medium=referral" target="_blank" rel="noreferrer">Unsplash</a>.
          </footer>
        </div>
      </main>
    </div>
  );
}
