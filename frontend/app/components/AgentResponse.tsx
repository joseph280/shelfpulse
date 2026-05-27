import type { AskResponse, Action } from "@/lib/types";

interface AgentResponseProps {
    response: AskResponse;
}

const leverColors: Record<string, string> = {
  promo: "bg-orange-100 text-orange-800",
  assortment: "bg-blue-100 text-blue-800",
  price: "bg-purple-100 text-purple-800",
  distribution: "bg-green-100 text-green-800",
  planogram: "bg-pink-100 text-pink-800",
  supply: "bg-yellow-100 text-yellow-800",
};

function formatUsd(n: number): string {
    if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
    return `$${n}`;
}

export function AgentResponse({ response }: AgentResponseProps) {
    const { insight, action_plan, trace_id } = response;
    
return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[90%] bg-agent-card border border-default rounded-2xl rounded-tl-md px-5 py-4 shadow-sm space-y-4">
        {/* Title */}
        <div>
          <h3 className="text-base font-semibold text-accent">{insight.title}</h3>
          <p className="text-xs text-muted mt-1">
            Confidence: {(insight.confidence * 100).toFixed(0)}%
          </p>
        </div>

        {/* Summary */}
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {insight.summary}
        </p>

        {/* Evidence list */}
        {insight.evidence.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted hover:text-accent">
              Evidence ({insight.evidence.length})
            </summary>
            <ul className="mt-2 space-y-1 pl-4">
              {insight.evidence.map((ev) => (
                <li key={ev.id} className="text-muted">
                  <span className="font-mono text-accent">[{ev.id}]</span>{" "}
                  {ev.metric} = {ev.value.toLocaleString()} ({ev.period})
                </li>
              ))}
            </ul>
          </details>
        )}

        {/* Action plan */}
        <div className="border-t border-default pt-3">
          <h4 className="text-sm font-semibold mb-2">
            Recommended actions ({action_plan.actions.length})
          </h4>
          <ol className="space-y-3">
            {action_plan.actions.map((action) => (
              <ActionRow key={action.rank} action={action} />
            ))}
          </ol>
        </div>

        {/* Trace ID */}
        <a  href="http://localhost:6006/projects"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-[10px] text-muted font-mono pt-2 border-t border-default hover:text-accent transition-colors"
        >
            trace_id: {trace_id} · view in Phoenix →
        </a>
      </div>
    </div>
  );
}

function ActionRow({ action }: { action: Action }) {
  const leverClass = leverColors[action.lever] ?? "bg-gray-100 text-gray-800";

  return (
    <li className="flex gap-3">
      <span className="flex-shrink-0 w-6 h-6 bg-accent text-white rounded-full text-xs font-bold flex items-center justify-center">
        {action.rank}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${leverClass}`}>
            {action.lever}
          </span>
          <span className="text-xs text-muted">{action.owner_role}</span>
          <span className="text-xs text-muted">·</span>
          <span className="text-xs text-muted">
            {formatUsd(action.expected_impact_low_usd)}–{formatUsd(action.expected_impact_high_usd)}
          </span>
        </div>
        <p className="text-sm leading-relaxed">{action.description}</p>
        <p className="text-[10px] text-muted font-mono mt-1">
          refs: {action.evidence_refs.join(", ")}
        </p>
      </div>
    </li>
  );
}