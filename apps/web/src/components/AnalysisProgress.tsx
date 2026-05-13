'use client'

import { AgentProgress } from '@/lib/api'

const AGENTS = [
  { key: 'hardware',     label: 'Hardware compatibility',  icon: '⬡' },
  { key: 'microgravity', label: 'Microgravity adaptation', icon: '◎' },
  { key: 'safety',       label: 'Safety screening',        icon: '◈' },
  { key: 'mission',      label: 'Mission integration',     icon: '◉' },
  { key: 'regulatory',   label: 'Regulatory pathway',      icon: '◫' },
]

interface AnalysisProgressProps {
  isActive: boolean
  completed: Record<string, AgentProgress>
  elapsed: number
}

export function AnalysisProgress({ isActive, completed, elapsed }: AnalysisProgressProps) {
  if (!isActive) return null

  return (
    <div className="rounded-xl border border-[var(--color-border-subtle)] bg-white p-5 max-w-[56rem] mx-auto">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-[var(--color-ink-primary)]">
          Running analysis
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
                <span className="flex gap-0.5">
                  {[0, 1, 2].map(i => (
                    <span
                      key={i}
                      className="w-1 h-1 rounded-full bg-[var(--color-ink-tertiary)] animate-pulse"
                      style={{ animationDelay: `${i * 200}ms` }}
                    />
                  ))}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
