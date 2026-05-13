'use client'

import { useState } from 'react'
import { ProtocolInput } from '@/components/ProtocolInput'
import { AnalysisReport } from '@/components/AnalysisReport'
import { AnalysisProgress } from '@/components/AnalysisProgress'
import { analyzeProtocol, type ProtocolRequirements, type OrchestratorReport } from '@/lib/api'

interface Message {
  role: 'user' | 'assistant'
  content: string | OrchestratorReport
  timestamp: Date
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(protocol: ProtocolRequirements) {
    setError(null)
    setIsLoading(true)

    setMessages(prev => [
      ...prev,
      { role: 'user', content: protocol.description, timestamp: new Date() },
    ])

    try {
      const report = await analyzeProtocol(protocol)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: report, timestamp: new Date() },
      ])
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Analysis failed. Is the API running?'
      setError(message)
      setMessages(prev => prev.slice(0, -1))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[var(--color-background)]">
      {/* Header */}
      <header className="border-b border-[var(--color-border-subtle)] bg-white sticky top-0 z-10">
        <div className="max-w-[56rem] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-[var(--color-accent)]" />
            <span className="font-serif text-base text-[var(--color-ink-primary)]">
              Spacebio Translator
            </span>
          </div>
          <span className="text-xs text-[var(--color-ink-tertiary)] font-mono">v0.1</span>
        </div>
      </header>

      {/* Conversation area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[56rem] mx-auto px-6 py-8 space-y-8">

          {/* Empty state */}
          {messages.length === 0 && !isLoading && (
            <div className="text-center py-20">
              <h1 className="font-serif text-3xl text-[var(--color-ink-primary)] mb-3 tracking-tight">
                Compliance analysis for biotech experiments destined for low-Earth orbit.
              </h1>
              <p className="text-[var(--color-ink-secondary)] max-w-prose mx-auto text-base leading-relaxed">
                Describe an experimental protocol. Get a multi-perspective analysis from
                five specialized agents covering hardware, microgravity adaptation, safety,
                mission integration, and regulatory pathway.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {[
                  'Arabidopsis plant growth study, 30 days, imaging required, BSL-1',
                  'CHO cell culture with CO2 control, media exchange, 14 days',
                  'Protein crystallization batch, 100 samples, no crew interaction needed',
                ].map(example => (
                  <button
                    key={example}
                    className="text-sm text-[var(--color-ink-tertiary)] border border-[var(--color-border-subtle)] rounded-full px-4 py-1.5 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
                    onClick={() => handleSubmit({ description: example })}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message history */}
          {messages.map((message, i) => (
            <div key={i}>
              {message.role === 'user' ? (
                <div className="flex justify-end mb-6">
                  <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-[var(--color-accent)] text-white px-5 py-3.5">
                    <p className="text-sm leading-relaxed">{message.content as string}</p>
                    <p className="text-xs opacity-60 mt-1.5 font-mono">
                      {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="mb-6">
                  <AnalysisReport report={message.content as OrchestratorReport} />
                </div>
              )}
            </div>
          ))}

          {/* Loading state */}
          {isLoading && <AnalysisProgress isActive={isLoading} />}

          {/* Error state */}
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4">
              <p className="text-sm text-red-700">{error}</p>
              <p className="text-xs text-red-500 mt-1">Check that your API is running on port 8000.</p>
            </div>
          )}
        </div>
      </div>

      {/* Input — fixed at bottom */}
      <div className="sticky bottom-0">
        <ProtocolInput onSubmit={handleSubmit} isLoading={isLoading} />
      </div>
    </div>
  )
}
