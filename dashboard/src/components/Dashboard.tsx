"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Aggregates } from "@/lib/aggregates.gen";
import { fetchAggregates } from "@/lib/api";
import { defaultWindowId, findWindow } from "@/lib/windows";
import { SyntheticBanner } from "./SyntheticBanner";
import { WindowPicker } from "./WindowPicker";
import { Tabs, type TabDef } from "./Tabs";
import { TopicsTab } from "./tabs/TopicsTab";
import { AdoptionTab } from "./tabs/AdoptionTab";
import { EngagementTab } from "./tabs/EngagementTab";
import { TimingTab } from "./tabs/TimingTab";
import { LanguageTab } from "./tabs/LanguageTab";

// Tab order is an editorial decision (2026-07-07): Topics first — the question
// the project exists to answer — then Adoption, Engagement, Timing, Language.
const TABS: TabDef[] = [
  { id: "topics", label: "Topics" },
  { id: "adoption", label: "Adoption" },
  { id: "engagement", label: "Engagement" },
  { id: "timing", label: "Timing" },
  { id: "language", label: "Language" },
];

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; doc: Aggregates };

export function Dashboard() {
  const searchParams = useSearchParams();
  const [state, setState] = useState<State>({ status: "loading" });
  const [tab, setTab] = useState<string>(() => {
    const fromUrl = searchParams.get("tab");
    return TABS.some((t) => t.id === fromUrl) ? (fromUrl as string) : TABS[0].id;
  });
  const [windowId, setWindowId] = useState<string | null>(() => searchParams.get("window"));

  useEffect(() => {
    fetchAggregates()
      .then((doc) => setState({ status: "ready", doc }))
      .catch((error: unknown) => setState({ status: "error", message: String(error) }));
  }, []);

  const doc = state.status === "ready" ? state.doc : null;

  // Resolve the selected window against the published registry; unknown or
  // missing ids fall back to the default (latest-coverage semester → all_time).
  const win = useMemo(() => {
    if (!doc) return null;
    return findWindow(doc.windows, windowId) ?? findWindow(doc.windows, defaultWindowId(doc.windows));
  }, [doc, windowId]);

  // Shareable state: ?tab=&window= (replaceState — no history spam, no reload).
  useEffect(() => {
    if (!win) return;
    const params = new URLSearchParams(globalThis.location.search);
    params.set("tab", tab);
    params.set("window", win.id);
    globalThis.history.replaceState(null, "", `?${params.toString()}`);
  }, [tab, win]);

  if (state.status === "loading") {
    return <div className="p-10 text-sm text-ink-3">Loading aggregates…</div>;
  }
  if (state.status === "error") {
    return (
      <div className="m-10 max-w-xl rounded-lg border border-edge bg-card p-6 text-sm">
        <p className="font-semibold text-ink">Could not load aggregates.</p>
        <p className="mt-1 text-ink-2">{state.message}</p>
        <p className="mt-3 text-ink-3">
          Retry by reloading the page. If this persists, check that the aggregates API is
          reachable.
        </p>
      </div>
    );
  }
  if (!doc || !win) return null;

  const panels: Record<string, React.ReactNode> = {
    topics: <TopicsTab doc={doc} win={win} />,
    adoption: <AdoptionTab doc={doc} win={win} />,
    engagement: <EngagementTab doc={doc} win={win} />,
    timing: <TimingTab doc={doc} win={win} />,
    language: <LanguageTab doc={doc} win={win} />,
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-6 pb-16 pt-6">
      <SyntheticBanner provenance={doc.data_provenance} />

      <header className="mt-8 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-3">
            University of Vienna · StatsBot
          </p>
          <h1 className="mt-1 font-display text-3xl text-ink">Educator dashboard</h1>
          <p className="mt-2 text-sm text-ink-2">
            Data through {doc.data_through_date} ({doc.data_through_week}), from week{" "}
            {doc.first_week} ·{" "}
            <span
              className="inline-flex cursor-help items-center gap-1 rounded-full border border-edge bg-card px-2 py-0.5 text-xs"
              title={`Aggregate cells covering fewer than ${doc.privacy_floor_n} students are withheld at aggregation time — shown as gray marks or "suppressed", never as zeros.`}
            >
              privacy floor N ≥ {doc.privacy_floor_n}
            </span>
          </p>
        </div>
        {/* Above the tab row and outside every panel: this filter scopes all tabs. */}
        <WindowPicker doc={doc} value={win.id} onChange={setWindowId} />
      </header>

      <nav className="mt-6">
        <Tabs tabs={TABS} active={tab} onSelect={setTab} />
      </nav>

      <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="mt-8">
        {panels[tab]}
      </div>

      <footer className="mt-14 border-t border-hairline pt-3 text-xs text-ink-3">
        pipeline {doc.pipeline_version} · schema {doc.schema_version} · labels{" "}
        {Object.entries(doc.label_versions)
          .map(([domain, version]) => `${domain}=${version}`)
          .join(", ") || "none"}{" "}
        · generated {doc.generated_at}
      </footer>
    </div>
  );
}
