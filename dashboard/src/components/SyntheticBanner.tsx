export function SyntheticBanner({ provenance }: { provenance: string }) {
  if (provenance === "production") return null;
  return (
    <div className="rounded-md border border-amber-400 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
      Synthetic demonstration data — no real student activity is shown. (data_provenance:{" "}
      <code>{provenance}</code>)
    </div>
  );
}
