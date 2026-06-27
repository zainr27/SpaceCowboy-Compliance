'use client'

import { memo, useEffect, useState } from 'react'
import { AgentProgress } from '@/lib/api'

const AGENTS = [
  { key: 'hardware',     label: 'Hardware compatibility',  icon: '⬡' },
  { key: 'microgravity', label: 'Microgravity adaptation', icon: '◎' },
  { key: 'safety',       label: 'Safety screening',        icon: '◈' },
  { key: 'mission',      label: 'Mission integration',     icon: '◉' },
  { key: 'regulatory',   label: 'Regulatory pathway',      icon: '◫' },
]

const PendingDots = () => (
  <span className="flex gap-0.5">
    {[0, 1, 2].map(i => (
      <span
        key={i}
        className="w-1 h-1 rounded-full bg-[var(--color-ink-tertiary)] animate-pulse"
        style={{ animationDelay: `${i * 200}ms` }}
      />
    ))}
  </span>
)

interface AnalysisProgressProps {
  completed: Record<string, AgentProgress>
  synthesizing: boolean
}

// Self-timed so the 10Hz elapsed counter re-renders ONLY this card, never the
// parent conversation tree (which holds the heavy, already-rendered reports).
function AnalysisProgressImpl({ completed, synthesizing }: AnalysisProgressProps) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = Date.now()
    const timer = setInterval(() => setElapsed(Date.now() - start), 100)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="rounded-xl border border-[var(--color-border-subtle)] bg-white p-5 max-w-[56rem] mx-auto">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-[var(--color-ink-primary)]">
          {synthesizing ? 'Synthesizing report' : 'Running analysis'}
        </span>
        <span className="text-xs font-mono text-[var(--color-ink-tertiary)]">
          {(elapsed / 1000).toFixed(1)}s
        </span>
      </div>

      <div className="space-y-2.5">
        {AGENTS.map(agent => {
          const progress = completed[agent.key]
          const isDone = !!progress

          return (
            <div key={agent.key} className="flex items-center gap-3">
              <span
                className="text-base transition-colors duration-300"
                style={{
                  color: isDone
                    ? progress.succeeded
                      ? 'var(--color-accent)'
                      : 'var(--color-error)'
                    : 'var(--color-ink-tertiary)',
                }}
              >
                {agent.icon}
              </span>
              <span
                className="text-sm transition-colors duration-300"
                style={{ color: isDone ? 'var(--color-ink-primary)' : 'var(--color-ink-tertiary)' }}
              >
                {agent.label}
              </span>
              <div className="flex-1" />
              {isDone ? (
                <span
                  className="text-xs font-mono"
                  style={{
                    color: progress.succeeded ? 'var(--color-success)' : 'var(--color-error)',
                  }}
                >
                  {progress.succeeded
                    ? `${(progress.duration_ms / 1000).toFixed(1)}s`
                    : 'failed'}
                </span>
              ) : (
                <PendingDots />
              )}
            </div>
          )
        })}

        {/* Synthesis step — fills the gap between the last agent and the report */}
        <div className="flex items-center gap-3 pt-2.5 mt-0.5 border-t border-[var(--color-border-subtle)]">
          <span
            className="text-base transition-colors duration-300"
            style={{ color: synthesizing ? 'var(--color-accent)' : 'var(--color-ink-tertiary)' }}
          >
            ✦
          </span>
          <span
            className="text-sm transition-colors duration-300"
            style={{ color: synthesizing ? 'var(--color-ink-primary)' : 'var(--color-ink-tertiary)' }}
          >
            Cross-agent synthesis
          </span>
          <div className="flex-1" />
          {synthesizing && <PendingDots />}
        </div>
      </div>
    </div>
  )
}

export const AnalysisProgress = memo(AnalysisProgressImpl)
