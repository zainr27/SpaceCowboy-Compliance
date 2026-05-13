'use client'

import { useState, useRef, useEffect } from 'react'
import { ProtocolInput } from '@/components/ProtocolInput'
import { AnalysisReport } from '@/components/AnalysisReport'
import { AnalysisProgress } from '@/components/AnalysisProgress'
import { analyzeProtocolStream, type ProtocolRequirements, type OrchestratorReport, type AgentProgress } from '@/lib/api'

interface Message {
  role: 'user' | 'assistant'
  content: string | OrchestratorReport
  timestamp: Date
}

const EXAMPLE_CHIPS = [
  {
    label: 'Arabidopsis plant growth, 30 days',
    description: 'A 30-day plant growth experiment with Arabidopsis thaliana, examining gravitropic response and seed-to-seed development under controlled humidity and light. Requires automated watering, CO2 regulation, imaging at 3-day intervals, and sample return at experiment end.',
  },
  {
    label: 'CHO cell culture with CO2 control',
    description: 'A 21-day cell culture experiment growing CHO cells at 37°C in DMEM medium with 5% CO2 supplementation. Media exchange required every 48 hours. Fluorescence imaging at days 0, 7, 14, and 21. Samples returned to Earth for downstream analysis.',
  },
  {
    label: 'Protein crystallization, 100 samples',
    description: 'Protein crystallization experiment using lysozyme as a model protein. Vapor diffusion method requiring 10 days of stable temperature at 20°C. 100 samples in parallel. No live organisms. Crystals must be returned to Earth for X-ray diffraction analysis.',
  },
]

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [completedAgents, setCompletedAgents] = useState<Record<string, AgentProgress>>({})
  const [elapsed, setElapsed] = useState(0)
  const conversationEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messages.length === 0 && !isLoading) return
    const timer = setTimeout(() => {
      conversationEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }, 100)
    return () => clearTimeout(timer)
  }, [messages, isLoading])

  async function handleSubmit(protocol: ProtocolRequirements) {
    setError(null)
    setIsLoading(true)
    setCompletedAgents({})
    setElapsed(0)

    setMessages(prev => [
      ...prev,
      { role: 'user', content: protocol.description, timestamp: new Date() },
    ])

    const startTime = Date.now()
    const timer = setInterval(() => setElapsed(Date.now() - startTime), 100)

    try {
      let finalReport: OrchestratorReport | null = null

      for await (const event of analyzeProtocolStream(protocol)) {
        if (event.type === 'progress') {
          setCompletedAgents(prev => ({
            ...prev,
            [event.agent]: { succeeded: event.succeeded, duration_ms: event.duration_ms },
          }))
        } else if (event.type === 'complete') {
          finalReport = event.report
        } else if (event.type === 'error') {
          throw new Error(event.message)
        }
      }

      if (finalReport) {
        setMessages(prev => [
          ...prev,
          { role: 'assistant', content: finalReport!, timestamp: new Date() },
        ])
        setInputValue('')
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Analysis failed. Is the API running?'
      setError(message)
      setMessages(prev => prev.slice(0, -1))
    } finally {
      clearInterval(timer)
      setIsLoading(false)
      setCompletedAgents({})
      setElapsed(0)
    }
  }

  return (
    <div className="h-screen flex flex-col bg-[var(--color-background)]">
      {/* Header */}
      <header className="border-b border-[var(--color-border-subtle)] bg-white shrink-0 z-10">
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

      {/* Conversation area — scrolls independently */}
      <div className="flex-1 overflow-y-auto min-h-0">
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
                {EXAMPLE_CHIPS.map(chip => (
                  <button
                    key={chip.label}
                    className="text-sm text-[var(--color-ink-tertiary)] border border-[var(--color-border-subtle)] rounded-full px-4 py-1.5 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
                    onClick={() => setInputValue(chip.description)}
                  >
                    {chip.label}
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
          {isLoading && (
            <AnalysisProgress
              isActive={isLoading}
              completed={completedAgents}
              elapsed={elapsed}
            />
          )}

          {/* Error state */}
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4">
              <p className="text-sm text-red-700">{error}</p>
              <p className="text-xs text-red-500 mt-1">Check that your API is running on port 8000.</p>
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={conversationEndRef} className="h-4" />
        </div>
      </div>

      {/* Input — pinned at bottom */}
      <div className="shrink-0">
        <ProtocolInput
          onSubmit={handleSubmit}
          isLoading={isLoading}
          value={inputValue}
          onChange={setInputValue}
          messageCount={messages.length}
        />
      </div>
    </div>
  )
}
