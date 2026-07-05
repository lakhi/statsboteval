"use client";

import { useEffect, useState } from "react";
import type { Aggregates } from "@/lib/aggregates.gen";
import { fetchAggregates } from "@/lib/api";
import { SyntheticBanner } from "@/components/SyntheticBanner";
import { WeeklyTrend } from "@/components/WeeklyTrend";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; doc: Aggregates };

export default function Home() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetchAggregates()
      .then((doc) => setState({ status: "ready", doc }))
      .catch((error: unknown) => setState({ status: "error", message: String(error) }));
  }, []);

  if (state.status === "loading") {
    return <main className="p-8 text-sm text-zinc-500">Loading aggregates…</main>;
  }
  if (state.status === "error") {
    return (
      <main className="p-8 text-sm text-red-700">
        Could not load aggregates: {state.message}
      </main>
    );
  }

  const doc = state.doc;
  const temporal = doc.sections.temporal_usage;
  const footnoteText = (ids?: string[] | null) =>
    (ids ?? []).map((id) => doc.footnotes[id]?.text ?? id);

  return (
    <main className="mx-auto w-full max-w-3xl space-y-4 p-6">
      <SyntheticBanner provenance={doc.data_provenance} />
      <header>
        <h1 className="text-xl font-bold text-zinc-900">StatsBot — educator dashboard</h1>
        <p className="text-sm text-zinc-500">
          Data through {doc.data_through_date} (week {doc.data_through_week}), from week {doc.first_week}.
          Privacy floor: cells covering fewer than {doc.privacy_floor_n} students are suppressed.
        </p>
      </header>
      {temporal ? (
        <div className="space-y-4">
          <WeeklyTrend
            title="Messages per week"
            entries={temporal.weekly.messages.series}
            floorN={doc.privacy_floor_n}
            footnotes={footnoteText(temporal.weekly.messages.footnote_ids)}
          />
          <WeeklyTrend
            title="Sessions per week"
            entries={temporal.weekly.sessions.series}
            floorN={doc.privacy_floor_n}
            footnotes={footnoteText(temporal.weekly.sessions.footnote_ids)}
          />
          <WeeklyTrend
            title="Active students per week"
            entries={temporal.weekly.active_students.series}
            floorN={doc.privacy_floor_n}
            footnotes={footnoteText(temporal.weekly.active_students.footnote_ids)}
          />
        </div>
      ) : (
        <p className="text-sm text-zinc-500">No temporal usage section in this publish.</p>
      )}
      <footer className="pt-2 text-xs text-zinc-400">
        pipeline {doc.pipeline_version} · schema {doc.schema_version} · generated {doc.generated_at}
      </footer>
    </main>
  );
}
