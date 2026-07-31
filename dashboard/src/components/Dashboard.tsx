"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Aggregates } from "@/lib/aggregates.gen";
import { fetchAggregates } from "@/lib/api";
import { formatGeneratedDate, formatWindowRange } from "@/lib/format";
import { ALL, LEVEL_LABELS, LEVEL_PHRASE, availableLevels, resolveLevel } from "@/lib/levels";
import { defaultWindowId, findWindow } from "@/lib/windows";
import { SyntheticBanner } from "./SyntheticBanner";
import { ProgramLevelPicker } from "./ProgramLevelPicker";
import { WindowPicker } from "./WindowPicker";
import { Tabs, type TabDef } from "./Tabs";
import { TopicsTab } from "./tabs/TopicsTab";
import { AdoptionTab } from "./tabs/AdoptionTab";
import { EngagementTab } from "./tabs/EngagementTab";
import { TimingTab } from "./tabs/TimingTab";
import { LanguageTab } from "./tabs/LanguageTab";
import { TrendsTab } from "./tabs/TrendsTab";

// Tab order is an editorial decision (2026-07-07): Topics first — the question
// the project exists to answer — then Adoption, Engagement, Timing, Language.
// Trends appended last (2026-07-30, D-49): it draws on the measures behind all five
// tabs, so it only makes sense once the reader has met them. Its cards link back to
// whichever tab a finding came from, which is the other reason it sits after them.
//
// `hidden` (2026-07-31, D-55) keeps Trends off the strip while leaving it reachable at
// ?tab=trends. Deleting the entry would have thrown away the reasoning above and made
// re-enabling a re-derivation; this way it is deleting one word.
const TABS: TabDef[] = [
  { id: "topics", label: "Topics" },
  { id: "adoption", label: "Adoption" },
  { id: "engagement", label: "Engagement" },
  { id: "timing", label: "Timing" },
  { id: "language", label: "Language" },
  { id: "trends", label: "Trends", hidden: true },
];
const VISIBLE_TABS = TABS.filter((t) => !t.hidden);

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; doc: Aggregates };

export function Dashboard() {
  const searchParams = useSearchParams();
  const [state, setState] = useState<State>({ status: "loading" });
  const [tab, setTab] = useState<string>(() => {
    // Checked against TABS, not VISIBLE_TABS: a hidden tab stays addressable by URL.
    const fromUrl = searchParams.get("tab");
    return TABS.some((t) => t.id === fromUrl) ? (fromUrl as string) : VISIBLE_TABS[0].id;
  });
  const [windowId, setWindowId] = useState<string | null>(() => searchParams.get("window"));
  // `?status=` keeps its name from the Topics-local control it replaces, so links shared
  // before D-55 still resolve to the level they named.
  const [levelId, setLevelId] = useState<string | null>(() => searchParams.get("status"));

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

  const levels = useMemo(() => (doc ? availableLevels(doc) : []), [doc]);
  const level = resolveLevel(levels, levelId);

  // Shareable state: ?tab=&window=&status= (replaceState — no history spam, no reload).
  useEffect(() => {
    if (!win) return;
    const params = new URLSearchParams(globalThis.location.search);
    params.set("tab", tab);
    params.set("window", win.id);
    params.set("status", level);
    globalThis.history.replaceState(null, "", `?${params.toString()}`);
  }, [tab, win, level]);

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
    topics: <TopicsTab doc={doc} win={win} level={level} />,
    adoption: <AdoptionTab doc={doc} win={win} level={level} />,
    engagement: <EngagementTab doc={doc} win={win} level={level} />,
    timing: <TimingTab doc={doc} win={win} level={level} />,
    language: <LanguageTab doc={doc} win={win} level={level} />,
    // setTab as a prop is fine here and below: this file is the "use client" entry
    // point, so nothing under it crosses the server/client boundary where function
    // props would have to be serializable.
    trends: <TrendsTab doc={doc} win={win} level={level} onJumpToTab={setTab} />,
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-6 pb-16 pt-6">
      <SyntheticBanner provenance={doc.data_provenance} />

      <header className="mt-8 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-3">
            StatsBotEval · University of Vienna
          </p>
          <h1 className="mt-1 font-display text-3xl text-ink">Educator Dashboard</h1>
          {/* Window- and level-scoped, like the pickers beside it: the sentence follows
              both filters rather than describing the whole published corpus. Naming the
              level here is a binding condition of making the filter global (D-55) —
              Bachelor is the default, so a reader who never touches the control is
              looking at a subset and has to be told so in the first sentence they read. */}
          <p className="mt-2 text-sm text-ink-2">
            Based on student–GenAI interactions data from StatsBot
            {level !== ALL ? <> — {LEVEL_PHRASE[level] ?? LEVEL_LABELS[level]}</> : null} (between{" "}
            {formatWindowRange(win)})
          </p>
        </div>
        {/* Above the tab row and outside every panel: these filters scope all tabs. */}
        <div className="flex flex-wrap items-center gap-3">
          <ProgramLevelPicker levels={levels} value={level} onChange={setLevelId} />
          <WindowPicker doc={doc} value={win.id} onChange={setWindowId} />
        </div>
      </header>

      <nav className="mt-6">
        <Tabs tabs={VISIBLE_TABS} active={tab} onSelect={setTab} />
      </nav>

      {/* aria-labelledby only when a rendered tab button carries that id: a hidden tab
          (?tab=trends) has no button, and pointing at a nonexistent element is worse for a
          screen reader than an explicit label. */}
      <div
        id={`panel-${tab}`}
        role="tabpanel"
        {...(VISIBLE_TABS.some((t) => t.id === tab)
          ? { "aria-labelledby": `tab-${tab}` }
          : { "aria-label": TABS.find((t) => t.id === tab)?.label ?? tab })}
        className="mt-8"
      >
        {panels[tab]}
      </div>

      <footer className="mt-14 border-t border-hairline pt-3 text-xs text-ink-3">
        pipeline {doc.pipeline_version} · schema {doc.schema_version} · labels{" "}
        {Object.entries(doc.label_versions)
          .map(([domain, version]) => `${domain}=${version}`)
          .join(", ") || "none"}{" "}
        ·{" "}
        <span
          className="cursor-help"
          title={`Aggregate cells covering fewer than ${doc.privacy_floor_n} students are withheld at aggregation time — shown as gray marks or "suppressed", never as zeros.`}
        >
          privacy floor N ≥ {doc.privacy_floor_n}
        </span>{" "}
        · generated {formatGeneratedDate(doc.generated_at, doc.timezone)}
      </footer>
    </div>
  );
}
