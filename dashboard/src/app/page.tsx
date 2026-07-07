import { Suspense } from "react";
import { Dashboard } from "@/components/Dashboard";

export default function Home() {
  return (
    <main className="flex-1">
      {/* useSearchParams in a static export requires a Suspense boundary
          (Next docs: app/api-reference/functions/use-search-params). */}
      <Suspense fallback={null}>
        <Dashboard />
      </Suspense>
    </main>
  );
}
