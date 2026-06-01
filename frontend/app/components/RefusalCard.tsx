import type { RefusalResponse } from "@/lib/types";
import { phoenixUrl } from "@/lib/api";

interface RefusalCardProps {
  refusal: RefusalResponse;
}

const reasonLabels: Record<string, string> = {
  out_of_scope: "Out of scope",
  pii: "PII detected",
  harmful: "Harmful content blocked",
  oversized_input: "Input too long or too short",
};

export function RefusalCard({ refusal }: RefusalCardProps) {
  const traceLink = phoenixUrl(refusal.phoenix_trace_id);
  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%] bg-refusal border border-refusal rounded-2xl rounded-tl-md px-5 py-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-yellow-200 text-yellow-900">
            {reasonLabels[refusal.reason] ?? refusal.reason}
          </span>
        </div>
        <p className="text-sm leading-relaxed">{refusal.message}</p>
        {traceLink ? (
          <a  href={traceLink}
              target="_blank"
              rel="noopener noreferrer"
              className="block text-[10px] text-muted font-mono mt-3 pt-2 border-t border-yellow-300 hover:text-yellow-900 transition-colors"
          >
              trace_id: {refusal.trace_id} · view in Phoenix →
          </a>
        ) : (
          <p className="block text-[10px] text-muted font-mono mt-3 pt-2 border-t border-yellow-300">
              trace_id: {refusal.trace_id}
          </p>
        )}
      </div>
    </div>
  );
}