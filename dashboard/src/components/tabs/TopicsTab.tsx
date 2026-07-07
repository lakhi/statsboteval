import { PanelIntro, type TabProps } from "./shared";

/**
 * Phase B teaser: `sections.topics` does not exist in v1 publishes. This panel
 * says what will land here and under which rules, instead of a bare
 * "coming soon". When the section ships it replaces this content additively
 * (contract §8) — v1 readers like this one simply start seeing data.
 */
export function TopicsTab({ doc }: TabProps) {
  return (
    <div>
      <PanelIntro
        question="What do students ask about?"
        deck="Topic distributions over the chat corpus — the question this project exists to answer. In development as Phase B (the classification pipeline)."
      />
      <div className="rounded-lg border border-edge bg-card p-6">
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold text-ink">Deductive — curriculum topics</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-2">
              Conversations assigned to predefined, curriculum-derived statistics topics (the
              Bergmann et&nbsp;al. codebook), so you can see which parts of the course drive
              StatsBot use.
            </p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-ink">Inductive — emergent themes</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-2">
              Finer, data-driven categories derived from the chats themselves — the struggles and
              question patterns no codebook anticipated.
            </p>
          </div>
        </div>
        <p className="mt-6 border-t border-hairline pt-3 text-xs leading-relaxed text-ink-3">
          Classification runs locally on the pseudonymized corpus; only aggregated,
          privacy-floored distributions are ever published here — chat text never leaves the
          local machine. Labels are versioned (
          <code className="font-mono">bergmann-v1</code> ·{" "}
          <code className="font-mono">statsboteval-v1</code>), and every figure will state which
          labeler produced it. Privacy floor N ≥ {doc.privacy_floor_n} applies as everywhere.
        </p>
      </div>
    </div>
  );
}
