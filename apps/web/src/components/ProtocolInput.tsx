'use client'

import { useState, useRef, useEffect } from 'react'
import { ProtocolRequirements } from '@/lib/api'

interface ProtocolInputProps {
  onSubmit: (protocol: ProtocolRequirements) => void
  isLoading: boolean
  value: string
  onChange: (value: string) => void
  messageCount: number
}

export function ProtocolInput({ onSubmit, isLoading, value, onChange, messageCount }: ProtocolInputProps) {
  const [showDetails, setShowDetails] = useState(false)
  const [details, setDetails] = useState<Partial<ProtocolRequirements>>({
    intent: 'research',
  })
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [value])

  function handleSubmit() {
    const trimmed = value.trim()
    if (trimmed.length < 50 || isLoading) return
    onSubmit({ description: trimmed, ...details })
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const canSubmit = value.trim().length >= 50 && !isLoading

  return (
    <div className="border-t border-[var(--color-border-subtle)] bg-white">
      <div className="max-w-[56rem] mx-auto px-6 py-4">

        <div className="mb-3">
          <button
            onClick={() => setShowDetails(v => !v)}
            className="text-xs text-[var(--color-ink-tertiary)] hover:text-[var(--color-ink-secondary)] transition-colors flex items-center gap-1"
          >
            <span className="font-mono">{showDetails ? '−' : '+'}</span>
            <span>Protocol details {showDetails ? '' : '(optional — improves analysis)'}</span>
          </button>
        </div>

        {showDetails && (
          <div className="grid grid-cols-2 gap-3 mb-4 p-4 rounded-lg bg-[var(--color-background)] border border-[var(--color-border-subtle)]">
            <div>
              <label className="text-xs text-[var(--color-ink-tertiary)] block mb-1">Organism</label>
              <input
                type="text"
                placeholder="e.g. CHO cells, Arabidopsis"
                value={details.organism || ''}
                onChange={e => setDetails(d => ({ ...d, organism: e.target.value || undefined }))}
                className="w-full text-sm px-3 py-1.5 rounded border border-[var(--color-border-subtle)] bg-white text-[var(--color-ink-primary)] placeholder:text-[var(--color-ink-tertiary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-ink-tertiary)] block mb-1">Duration (days)</label>
              <input
                type="number"
                placeholder="e.g. 14"
                value={details.duration_days || ''}
                onChange={e => setDetails(d => ({ ...d, duration_days: e.target.value ? parseInt(e.target.value) : undefined }))}
                className="w-full text-sm px-3 py-1.5 rounded border border-[var(--color-border-subtle)] bg-white text-[var(--color-ink-primary)] placeholder:text-[var(--color-ink-tertiary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-ink-tertiary)] block mb-1">Temperature (°C)</label>
              <input
                type="number"
                placeholder="e.g. 37"
                value={details.temperature_c || ''}
                onChange={e => setDetails(d => ({ ...d, temperature_c: e.target.value ? parseFloat(e.target.value) : undefined }))}
                className="w-full text-sm px-3 py-1.5 rounded border border-[var(--color-border-subtle)] bg-white text-[var(--color-ink-primary)] placeholder:text-[var(--color-ink-tertiary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-ink-tertiary)] block mb-1">CO₂ (%)</label>
              <input
                type="number"
                placeholder="e.g. 5"
                value={details.co2_pct || ''}
                onChange={e => setDetails(d => ({ ...d, co2_pct: e.target.value ? parseFloat(e.target.value) : undefined }))}
                className="w-full text-sm px-3 py-1.5 rounded border border-[var(--color-border-subtle)] bg-white text-[var(--color-ink-primary)] placeholder:text-[var(--color-ink-tertiary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-ink-tertiary)] block mb-1">Biosafety level</label>
              <select
                value={details.biosafety_level || ''}
                onChange={e => setDetails(d => ({ ...d, biosafety_level: (e.target.value as 'BSL-1' | 'BSL-2' | 'BSL-3') || undefined }))}
                className="w-full text-sm px-3 py-1.5 rounded border border-[var(--color-border-subtle)] bg-white text-[var(--color-ink-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              >
                <option value="">Unknown</option>
                <option value="BSL-1">BSL-1</option>
                <option value="BSL-2">BSL-2</option>
                <option value="BSL-3">BSL-3</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-[var(--color-ink-tertiary)] block mb-1">Intent</label>
              <select
                value={details.intent || 'research'}
                onChange={e => setDetails(d => ({ ...d, intent: e.target.value as 'research' | 'commercial' | 'clinical_pathway' }))}
                className="w-full text-sm px-3 py-1.5 rounded border border-[var(--color-border-subtle)] bg-white text-[var(--color-ink-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              >
                <option value="research">Research</option>
                <option value="commercial">Commercial</option>
                <option value="clinical_pathway">Clinical pathway</option>
              </select>
            </div>

            <div className="col-span-2 flex gap-4 flex-wrap">
              {[
                { key: 'requires_media_exchange', label: 'Media exchange' },
                { key: 'requires_imaging', label: 'Imaging' },
                { key: 'requires_sample_return', label: 'Sample return' },
                { key: 'light_required', label: 'Light required' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-1.5 text-xs text-[var(--color-ink-secondary)] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={(details as Record<string, boolean | undefined>)[key] || false}
                    onChange={e => setDetails(d => ({ ...d, [key]: e.target.checked || undefined }))}
                    className="accent-[var(--color-accent)]"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={e => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your experimental protocol. What organism, what conditions, what are you trying to measure? (minimum 50 characters)"
              rows={1}
              disabled={isLoading}
              className="w-full resize-none text-sm px-4 py-3 rounded-xl border border-[var(--color-border)] bg-white text-[var(--color-ink-primary)] placeholder:text-[var(--color-ink-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:border-transparent transition-shadow disabled:opacity-50 leading-relaxed"
              style={{ minHeight: '48px', maxHeight: '200px' }}
            />
            <div className="absolute bottom-2.5 right-3 text-[10px] text-[var(--color-ink-tertiary)] font-mono pointer-events-none">
              {value.length < 50 ? `${50 - value.length} more` : '⌘↵'}
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!canSubmit && !isLoading}
            className={`px-4 py-3 rounded-xl text-white text-sm font-medium transition-all flex-shrink-0 h-[48px] ${
              isLoading
                ? 'bg-[var(--color-accent)] opacity-70 cursor-wait'
                : canSubmit
                ? 'bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] cursor-pointer'
                : 'bg-[var(--color-accent)] opacity-30 cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                Running
              </span>
            ) : (
              'Analyze'
            )}
          </button>
        </div>

        {messageCount === 0 ? (
          <p className="text-xs text-[var(--color-ink-tertiary)] mt-2">
            Five agents run in parallel: hardware compatibility, microgravity adaptation, safety screening, mission integration, regulatory pathway.
          </p>
        ) : (
          <p className="text-xs text-[var(--color-ink-tertiary)] mt-2">
            Submit another protocol to add to the conversation.
          </p>
        )}
      </div>
    </div>
  )
}
