const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ProtocolRequirements {
  description: string
  organism?: string
  duration_days?: number
  sample_count?: number
  temperature_c?: number
  humidity_pct?: number
  co2_pct?: number
  light_required?: boolean
  requires_media_exchange?: boolean
  requires_imaging?: boolean
  requires_sample_return?: boolean
  biosafety_level?: 'BSL-1' | 'BSL-2' | 'BSL-3'
  intent?: 'research' | 'commercial' | 'clinical_pathway'
}

export interface OrchestratorReport {
  protocol: ProtocolRequirements
  total_duration_ms: number
  executor: string
  synthesizer: string
  agent_executions: Array<{
    agent: 'hardware' | 'microgravity' | 'safety' | 'mission' | 'regulatory'
    succeeded: boolean
    duration_ms: number
    chunks_used: number
    error: string | null
  }>
  executive_summary: {
    headline: string
    facility_recommendation: string | null
    primary_microgravity_concern: string | null
    biosafety_classification: string
    mission_pathway: string | null
    regulatory_floor: string
  }
  confidence: {
    hardware: number | null
    microgravity: number | null
    safety: number | null
    mission: number | null
    regulatory: number | null
    overall: number
  }
  hardware: unknown | null
  microgravity: unknown | null
  safety: unknown | null
  mission: unknown | null
  regulatory: unknown | null
  cross_agent_insights: Array<{
    kind: 'consistency_check' | 'tension' | 'compound_risk' | 'corpus_gap'
    description: string
    involved_agents: string[]
  }>
  citations: Array<{
    unified_index: number
    chunk_id: string
    document_id: string
    title: string
    source_url: string
    page_number: number | null
    section_path: string | null
    relevance_score: number
    cited_by: string[]
  }>
  open_questions: string[]
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function analyzeProtocol(
  protocol: ProtocolRequirements,
): Promise<OrchestratorReport> {
  const response = await fetch(`${API_BASE_URL}/agents/orchestrator/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(protocol),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new ApiError(errorText || `Request failed: ${response.status}`, response.status)
  }

  return response.json()
}
