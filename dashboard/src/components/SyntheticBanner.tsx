export function SyntheticBanner({ provenance }: { provenance: string }) {
  if (provenance === "production") return null;
  return (
    <div className="rounded-md border border-notice-edge bg-notice-bg px-4 py-3 text-sm font-medium text-notice-ink">
      Synthetic demonstration data — no real student activity is shown. (data_provenance:{" "}
      <code className="font-mono text-[0.85em]">{provenance}</code>)
    </div>
  );
}
