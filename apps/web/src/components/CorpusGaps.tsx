'use client'

import { useEffect, useState } from 'react'
import { getGapBacklog, type GapBacklog } from '@/lib/api'

// "Ingest these next" — the questions and themes past analyses most often
// could not ground in the corpus. The system curating its own corpus needs.
export function CorpusGaps() {
  const [backlog, setBacklog] = useState<GapBacklog | null>(null)

  useEffect(() => {
    let cancelled = false
    getGapBacklog()
      .then(b => {
        if (!cancelled) setBacklog(b)
      })
      .catch(() => {
        /* advisory panel — stay silent if the API isn't up */
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!backlog || backlog.total_runs === 0) return null
  const { recurring_questions, gap_themes } = backlog
  if (recurring_questions.length === 0 && gap_themes.length === 0) return null

  return (
    <div className="mt-12 max-w-prose mx-auto text-left">
      <h3 className="text-xs font-medium text-[var(--color-ink-tertiary)] uppercase tracking-wider mb-3">
        What the corpus is missing · from {backlog.total_runs} past{' '}
        {backlog.total_runs === 1 ? 'analysis' : 'analyses'}
      </h3>

      {gap_themes.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {gap_themes.map((t, i) => (
            <span
              key={i}
              className="text-xs rounded-full border border-[var(--color-accent-light)] bg-[var(--color-accent-subtle)] text-[var(--color-ink-secondary)] px-3 py-1"
              title={t.theme}
            >
              {t.agents.join(' · ')}
              {t.count > 1 ? ` ×${t.count}` : ''}
            </span>
          ))}
        </div>
      )}

      <ul className="space-y-1.5">
        {recurring_questions.slice(0, 6).map((q, i) => (
          <li key={i} className="flex gap-2.5 text-sm text-[var(--color-ink-secondary)]">
            <span className="font-mono text-xs text-[var(--color-accent)] shrink-0 mt-0.5">
              {q.count > 1 ? `×${q.count}` : '·'}
            </span>
            <span className="leading-snug">{q.question}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
