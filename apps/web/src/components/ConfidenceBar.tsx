interface ConfidenceBarProps {
  score: number
  label?: string
  showScore?: boolean
  size?: 'sm' | 'md'
}

function confidenceColor(score: number): string {
  if (score >= 0.7) return 'var(--color-confidence-high)'
  if (score >= 0.4) return 'var(--color-confidence-medium)'
  return 'var(--color-confidence-low)'
}

export function ConfidenceBar({
  score,
  label,
  showScore = true,
  size = 'md',
}: ConfidenceBarProps) {
  const color = confidenceColor(score)
  const height = size === 'sm' ? 'h-1' : 'h-1.5'

  return (
    <div className="flex items-center gap-2.5">
      {label && (
        <span className="text-xs text-[var(--color-ink-tertiary)] w-24 shrink-0">{label}</span>
      )}
      <div className={`flex-1 ${height} rounded-full bg-[var(--color-border-subtle)] overflow-hidden`}>
        <div
          className={`${height} rounded-full transition-all duration-700`}
          style={{
            width: `${Math.round(score * 100)}%`,
            backgroundColor: color,
          }}
        />
      </div>
      {showScore && (
        <span
          className="text-xs font-mono tabular-nums w-8 shrink-0"
          style={{ color }}
        >
          {score.toFixed(2)}
        </span>
      )}
    </div>
  )
}
