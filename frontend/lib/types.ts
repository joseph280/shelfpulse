/**
 * Mirrors api/schemas.py from the backend
 * Keep these in sync the the backend schemas change
 */

export type ActionLever =
  | "promo"
  | "assortment"
  | "price"
  | "distribution"
  | "planogram"
  | "supply";

export type OwnerRole =
  | "Category Manager"
  | "Demand Planner"
  | "Trade Marketing"
  | "Supply Chain";

export type RefusalReason =
  | "out_of_scope"
  | "harmful"
  | "pii"
  | "oversized_input";

export interface Evidence {
    id: string;    // ev-N
    metric: string;
    value: number;
    period: string;
    filter: Record<string, string>;
    source_tool: string;
}

export interface Insight {
    id: string;    // ins-<uuid>
    title: string;
    summary: string;
    evidence: Evidence[];
    confidence: number;  // 0.0 to 1.0
}

export interface Action {
    rank: number;
    lever: ActionLever;
    description: string;
    expected_impact_low_usd: number;
    expected_impact_high_usd: number;
    confidence: number;  
    owner_role: OwnerRole;
    evidence_refs: string[];
}

export interface ActionPlan {
    id: string;    // ap-<uuid>
    actions: Action[];
    generated_at: string;  // ISO timestamp
}


export interface AskRequest {
    question: string;
    max_tokens?: number;
    temperature?: number;
}

export interface AskResponse {
    trace_id: string;
    insight: Insight;
    action_plan: ActionPlan;
    low_confidence: boolean;
    phoenix_trace_id?: string | null;
}

export interface RefusalResponse {
    trace_id: string;
    reason: RefusalReason;
    message: string;
    phoenix_trace_id?: string | null;
}

/**
 * Union type for /ask responses. Distinguish by presence of `insight`:
 *   - if "insight" in response → AskResponse
 *   - otherwise → RefusalResponse
 */
export type AskResult = AskResponse | RefusalResponse;

/**
 * Type guard to narrow AskResult.
 */
export function isRefusal(result: AskResult): result is RefusalResponse {
    return !("insight" in result);
}

export interface HealthStatus{
    status: "ok" | "degraded";
    anthropic_key?: "present" | "missing";
    warehouse_rows?: string;
    warehouse?: string;
}