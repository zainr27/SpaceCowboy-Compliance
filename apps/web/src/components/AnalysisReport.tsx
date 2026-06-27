'use client'

import { memo, useState } from 'react'
import { OrchestratorReport } from '@/lib/api'
import { ConfidenceBar } from './ConfidenceBar'

// ── Finding pill ──────────────────────────────────────────────────────────────

function FindingPill({ label, value, className = '' }: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className={`rounded-lg bg-[var(--color-background)] px-3 py-2.5 ${className}`}>
      <span className="text-xs text-[var(--color-ink-tertiary)] block mb-0.5">{label}</span>
      <span className="text-sm text-[var(--color-ink-primary)]">{value}</span>
    </div>
  )
}

// ── Executive summary ─────────────────────────────────────────────────────────

function ExecutiveSummaryCard({ summary, confidence }: {
  summary: OrchestratorReport['executive_summary']
  confidence: OrchestratorReport['confidence']
}) {
  // Soft signal for borderline in-scope runs: low aggregate confidence, or any
  // single agent very unsure, means the grounding may be weak — say so plainly
  // instead of letting the headline read as authoritative.
  const agentScores = [
    confidence.hardware,
    confidence.microgravity,
    confidence.safety,
    confidence.mission,
    confidence.regulatory,
  ].filter((s): s is number => s !== null && s !== undefined)
  const minAgent = agentScores.length ? Math.min(...agentScores) : 1
  const lowConfidence = confidence.overall < 0.5 || minAgent < 0.35

  return (
    <div className="rounded-xl border border-[var(--color-border-subtle)] bg-white overflow-hidden">
      <div className="h-0.5 bg-[var(--color-accent)]" />
      <div className="p-6">
        {lowConfidence && (
          <div className="flex gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 mb-5">
            <span className="text-amber-500 shrink-0">△</span>
            <p className="text-xs text-amber-800 leading-relaxed">
              Low confidence — the corpus may not cover this protocol well. Treat these
              findings as tentative and verify against primary sources.
            </p>
          </div>
        )}
        <div className="flex items-start justify-between gap-4 mb-5">
          <h2 className="font-serif text-xl text-[var(--color-ink-primary)] leading-snug">
            {summary.headline}
          </h2>
          <span className="text-xs font-mono text-[var(--color-ink-tertiary)] shrink-0 mt-1">
            {Math.round(confidence.overall * 100)}% confidence
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-5">
          {summary.biosafety_classification && (
            <FindingPill label="Biosafety" value={summary.biosafety_classification} />
          )}
          {summary.facility_recommendation && (
            <FindingPill label="Facility" value={summary.facility_recommendation} />
          )}
          {summary.primary_microgravity_concern && (
            <FindingPill label="Microgravity" value={summary.primary_microgravity_concern} />
          )}
          {summary.mission_pathway && (
            <FindingPill label="Mission" value={summary.mission_pathway} />
          )}
          {summary.regulatory_floor && (
            <FindingPill label="Regulatory floor" value={summary.regulatory_floor} className="col-span-2" />
          )}
        </div>

        <div className="space-y-2 pt-4 border-t border-[var(--color-border-subtle)]">
          <span className="text-xs text-[var(--color-ink-tertiary)]">Agent confidence</span>
          {(Object.entries({
            Hardware: confidence.hardware,
            Microgravity: confidence.microgravity,
            Safety: confidence.safety,
            Mission: confidence.mission,
            Regulatory: confidence.regulatory,
          }) as [string, number | null][]).map(([label, score]) =>
            score !== null && score !== undefined ? (
              <ConfidenceBar key={label} label={label} score={score} size="sm" />
            ) : null
          )}
        </div>
      </div>
    </div>
  )
}

// ── Cross-agent insights ──────────────────────────────────────────────────────

const insightStyles: Record<string, { bg: string; border: string; label: string; dot: string }> = {
  corpus_gap: {
    bg: 'bg-[var(--color-accent-subtle)]',
    border: 'border-[var(--color-accent-light)]',
    label: 'Corpus gap',
    dot: 'bg-[var(--color-accent)]',
  },
  tension: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    label: 'Tension',
    dot: 'bg-amber-500',
  },
  compound_risk: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    label: 'Compound risk',
    dot: 'bg-red-500',
  },
  consistency_check: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    label: 'Consistency check',
    dot: 'bg-green-500',
  },
}

function CrossAgentInsights({ insights }: {
  insights: OrchestratorReport['cross_agent_insights']
}) {
  if (!insights.length) return null

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium text-[var(--color-ink-tertiary)] uppercase tracking-wider">
        Cross-agent insights
      </h3>
      {insights.map((insight, i) => {
        const style = insightStyles[insight.kind] ?? insightStyles.consistency_check
        return (
          <div key={i} className={`rounded-lg border px-4 py-3 ${style.bg} ${style.border}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
              <span className="text-xs font-medium text-[var(--color-ink-secondary)]">
                {style.label}
              </span>
              <span className="text-xs text-[var(--color-ink-tertiary)]">
                {insight.involved_agents.join(' · ')}
              </span>
            </div>
            <p className="text-sm text-[var(--color-ink-primary)]">{insight.description}</p>
          </div>
        )
      })}
    </div>
  )
}

// ── Collapsible agent section ─────────────────────────────────────────────────

export function AgentSection({ title, confidence, children, defaultOpen = false }: {
  title: string
  confidence: number | null | undefined
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="rounded-xl border border-[var(--color-border-subtle)] bg-white overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-[var(--color-surface-hover)] transition-colors"
      >
        <div className="flex items-center gap-4 min-w-0">
          <span className="text-sm font-medium text-[var(--color-ink-primary)]">{title}</span>
          {confidence !== null && confidence !== undefined && (
            <div className="w-24 shrink-0">
              <ConfidenceBar score={confidence} showScore size="sm" />
            </div>
          )}
        </div>
        <span className="text-[var(--color-ink-tertiary)] text-sm ml-4 shrink-0">
          {open ? '↑' : '↓'}
        </span>
      </button>

      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-[var(--color-border-subtle)]">
          {children}
        </div>
      )}
    </div>
  )
}

// ── Citations ─────────────────────────────────────────────────────────────────

function CitationList({ citations }: { citations: OrchestratorReport['citations'] }) {
  if (!citations.length) return null

  return (
    <div>
      <h3 className="text-xs font-medium text-[var(--color-ink-tertiary)] uppercase tracking-wider mb-3">
        Sources · {citations.length} unique
      </h3>
      <div className="space-y-2">
        {citations.map(c => (
          <div
            key={c.chunk_id}
            className="flex gap-3 text-sm py-2 border-b border-[var(--color-border-subtle)] last:border-0"
          >
            <span className="font-mono text-xs text-[var(--color-accent)] w-6 shrink-0 mt-0.5">
              [{c.unified_index}]
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-[var(--color-ink-primary)] leading-snug">{c.title}</p>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                {c.page_number && (
                  <span className="text-xs text-[var(--color-ink-tertiary)]">p. {c.page_number}</span>
                )}
                <span className="text-xs text-[var(--color-ink-tertiary)]">
                  cited by {c.cited_by.join(', ')}
                </span>
                <span className="text-xs font-mono text-[var(--color-ink-tertiary)]">
                  {c.relevance_score.toFixed(3)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Open questions ────────────────────────────────────────────────────────────

function OpenQuestions({ questions }: { questions: string[] }) {
  if (!questions.length) return null

  return (
    <div className="rounded-xl border border-[var(--color-accent-light)] bg-[var(--color-accent-subtle)] p-5">
      <h3 className="text-xs font-medium text-[var(--color-accent)] uppercase tracking-wider mb-3">
        Open questions · require external review
      </h3>
      <ul className="space-y-2">
        {questions.map((q, i) => (
          <li key={i} className="flex gap-2.5 text-sm text-[var(--color-ink-secondary)]">
            <span className="font-mono text-[var(--color-accent)] shrink-0">{i + 1}.</span>
            {q}
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── Agent content renderers ───────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function HardwareContent({ data }: { data: any }) {
  if (!data?.analysis) return <p className="text-sm text-[var(--color-ink-tertiary)]">No data</p>
  const { summary, recommended_hardware, gaps } = data.analysis
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-[var(--color-ink-secondary)]">{summary}</p>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {recommended_hardware?.map((hw: any, i: number) => (
        <div key={i} className="rounded-lg bg-[var(--color-background)] p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-[var(--color-ink-primary)]">{hw.name}</span>
            <span className="text-xs font-mono text-[var(--color-ink-tertiary)]">
              fit {hw.fit_score?.toFixed(2)}
            </span>
          </div>
          <p className="text-sm text-[var(--color-ink-secondary)]">{hw.rationale}</p>
          {hw.constraints?.length > 0 && (
            <ul className="mt-2 space-y-1">
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              {hw.constraints.map((c: any, j: number) => (
                <li key={j} className="text-xs text-[var(--color-ink-tertiary)] flex gap-1.5">
                  <span>·</span>{c}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {gaps?.map((gap: any, i: number) => (
        <div key={i} className="text-sm text-[var(--color-ink-tertiary)] flex gap-2">
          <span className="text-[var(--color-warning)] shrink-0">△</span>
          <span>{gap.requirement}: {gap.notes}</span>
        </div>
      ))}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function MicrogravityContent({ data }: { data: any }) {
  if (!data?.analysis) return <p className="text-sm text-[var(--color-ink-tertiary)]">No data</p>
  const { summary, modifications, research_precedents } = data.analysis
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-[var(--color-ink-secondary)]">{summary}</p>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {modifications?.map((mod: any, i: number) => (
        <div key={i} className="rounded-lg bg-[var(--color-background)] p-4 space-y-2">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              mod.severity === 'critical'
                ? 'bg-red-100 text-red-700'
                : mod.severity === 'important'
                ? 'bg-amber-100 text-amber-700'
                : 'bg-green-100 text-green-700'
            }`}>
              {mod.severity}
            </span>
            <span className="text-xs text-[var(--color-ink-tertiary)]">{mod.aspect}</span>
          </div>
          <div className="space-y-1.5">
            <div>
              <span className="text-xs text-[var(--color-ink-tertiary)]">Earth assumption: </span>
              <span className="text-xs text-[var(--color-ink-secondary)]">{mod.earthbound_assumption}</span>
            </div>
            <div>
              <span className="text-xs text-[var(--color-ink-tertiary)]">Microgravity reality: </span>
              <span className="text-xs text-[var(--color-ink-secondary)]">{mod.microgravity_reality}</span>
            </div>
            <div className="pt-1">
              <span className="text-xs font-medium text-[var(--color-ink-primary)]">Recommended: </span>
              <span className="text-xs text-[var(--color-ink-primary)]">{mod.recommended_change}</span>
            </div>
          </div>
        </div>
      ))}
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {research_precedents?.map((p: any, i: number) => (
        <div key={i} className="text-sm text-[var(--color-ink-secondary)] flex gap-2.5">
          <span className="text-[var(--color-info)] shrink-0">◎</span>
          <div>
            <span className="font-medium">{p.description}: </span>
            {p.finding}
          </div>
        </div>
      ))}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function SafetyContent({ data }: { data: any }) {
  if (!data?.analysis) return <p className="text-sm text-[var(--color-ink-tertiary)]">No data</p>
  const { summary, biosafety_classification, hazards, review_milestones } = data.analysis
  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-[var(--color-ink-primary)]">BSL Classification:</span>
        <span className="text-sm font-mono text-[var(--color-accent)]">{biosafety_classification}</span>
      </div>
      <p className="text-sm text-[var(--color-ink-secondary)]">{summary}</p>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {hazards?.map((h: any, i: number) => (
        <div key={i} className="rounded-lg bg-[var(--color-background)] p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs text-[var(--color-ink-tertiary)]">{h.category}</span>
            <span className="text-xs font-mono text-[var(--color-ink-tertiary)]">
              {h.severity} · {h.likelihood} likelihood
            </span>
          </div>
          <p className="text-sm text-[var(--color-ink-secondary)]">{h.description}</p>
          <p className="text-xs text-[var(--color-ink-tertiary)] mt-1.5">
            <span className="font-medium">Mitigation: </span>{h.mitigation}
          </p>
        </div>
      ))}
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {review_milestones?.map((m: any, i: number) => (
        <div key={i} className="text-sm flex gap-2.5">
          <span className="text-[var(--color-accent)] shrink-0 font-mono text-xs mt-0.5">{i + 1}.</span>
          <div>
            <span className="font-medium text-[var(--color-ink-primary)]">{m.phase}</span>
            {m.typical_timing && (
              <span className="text-[var(--color-ink-tertiary)] text-xs ml-2">{m.typical_timing}</span>
            )}
            <p className="text-xs text-[var(--color-ink-secondary)] mt-0.5">{m.required_documentation}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function MissionContent({ data }: { data: any }) {
  if (!data?.analysis) return <p className="text-sm text-[var(--color-ink-tertiary)]">No data</p>
  const { summary, recommended_facilities, ascent_options, resource_budget, crew_time } = data.analysis
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-[var(--color-ink-secondary)]">{summary}</p>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {recommended_facilities?.map((f: any, i: number) => (
        <div key={i} className="rounded-lg bg-[var(--color-background)] p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-sm font-medium text-[var(--color-ink-primary)]">{f.facility_name}</span>
            <span className="text-xs text-[var(--color-ink-tertiary)]">{f.provider}</span>
          </div>
          <p className="text-sm text-[var(--color-ink-secondary)]">{f.fit_rationale}</p>
        </div>
      ))}
      {resource_budget && (
        <div className="grid grid-cols-2 gap-2">
          <FindingPill
            label="Cold stowage"
            value={resource_budget.requires_cold_stowage ? 'Required' : 'Not required'}
          />
          <FindingPill
            label="Crew interaction"
            value={crew_time?.interaction_type || 'unspecified'}
          />
          {ascent_options?.[0] && (
            <FindingPill
              label="Ascent vehicle"
              value={ascent_options[0].vehicle.replace(/_/g, ' ')}
              className="col-span-2"
            />
          )}
        </div>
      )}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function RegulatoryContent({ data }: { data: any }) {
  if (!data?.analysis) return <p className="text-sm text-[var(--color-ink-tertiary)]">No data</p>
  const { summary, applicable_frameworks } = data.analysis
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-[var(--color-ink-secondary)]">{summary}</p>
      {applicable_frameworks
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ?.filter((f: any) => f.applicability !== 'not_applicable')
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .map((f: any, i: number) => (
          <div key={i} className="flex gap-3">
            <span
              className="text-xs font-mono shrink-0 mt-0.5"
              style={{
                color: f.applicability === 'required'
                  ? 'var(--color-error)'
                  : f.applicability === 'likely_applicable'
                  ? 'var(--color-warning)'
                  : 'var(--color-ink-tertiary)',
              }}
            >
              {f.applicability === 'required' ? '●' : f.applicability === 'likely_applicable' ? '◐' : '○'}
            </span>
            <div>
              <span className="text-sm font-medium text-[var(--color-ink-primary)]">
                {f.framework.replace(/_/g, ' ')}
              </span>
              <p className="text-xs text-[var(--color-ink-tertiary)] mt-0.5">{f.rationale}</p>
            </div>
          </div>
        ))}
    </div>
  )
}

// ── Agent sections (shared by the live reveal and the final report) ────────────

export type AgentKey = 'hardware' | 'microgravity' | 'safety' | 'mission' | 'regulatory'

const AGENT_SECTIONS: Array<{
  key: AgentKey
  title: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  Content: ({ data }: { data: any }) => React.ReactNode
}> = [
  { key: 'hardware', title: 'Hardware Compatibility', Content: HardwareContent },
  { key: 'microgravity', title: 'Microgravity Adaptation', Content: MicrogravityContent },
  { key: 'safety', title: 'Safety Screening', Content: SafetyContent },
  { key: 'mission', title: 'Mission Integration', Content: MissionContent },
  { key: 'regulatory', title: 'Regulatory Pathway', Content: RegulatoryContent },
]

/**
 * Renders one collapsible card per agent. Used live (only agents that have
 * streamed in are passed) and in the final report (all five). A section is
 * rendered when its key is present in `outputs`, even if the value is null
 * (a failed agent shows "No data").
 */
export function AgentSections({
  outputs,
  confidence,
}: {
  outputs: Partial<Record<AgentKey, unknown>>
  confidence: Partial<Record<AgentKey, number | null>>
}) {
  return (
    <>
      {AGENT_SECTIONS.filter(s => s.key in outputs).map((s, i) => (
        <div key={s.key} className="animate-fade-up">
          <AgentSection title={s.title} confidence={confidence[s.key]} defaultOpen={i === 0}>
            <s.Content data={outputs[s.key]} />
          </AgentSection>
        </div>
      ))}
    </>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export const AnalysisReport = memo(function AnalysisReport({ report }: { report: OrchestratorReport }) {
  return (
    <div className="space-y-4 max-w-[56rem] mx-auto">
      <div className="flex items-center gap-3 text-xs text-[var(--color-ink-tertiary)] font-mono">
        <span>{(report.total_duration_ms / 1000).toFixed(1)}s</span>
        <span>·</span>
        <span>{report.agent_executions.filter(e => e.succeeded).length}/5 agents</span>
        <span>·</span>
        <span>{report.citations.length} sources</span>
      </div>

      <ExecutiveSummaryCard summary={report.executive_summary} confidence={report.confidence} />

      <CrossAgentInsights insights={report.cross_agent_insights} />

      <AgentSections
        outputs={{
          hardware: report.hardware,
          microgravity: report.microgravity,
          safety: report.safety,
          mission: report.mission,
          regulatory: report.regulatory,
        }}
        confidence={report.confidence}
      />

      <CitationList citations={report.citations} />
      <OpenQuestions questions={report.open_questions} />
    </div>
  )
})
