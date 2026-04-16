import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { jobsApi, vendorsApi, domainsApi } from '@/api/client'
import { useWebSocket } from '@/context/WebSocketContext'
import StatusBadge from '@/components/StatusBadge'
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react'

function AnsiLog({ text }: { text: string }) {
  if (!text) return <span className="text-muted-foreground/40">No logs captured for this vendor.</span>

  const ansiColors: Record<string, string> = {
    '30': '#6b7280', '31': '#ef4444', '32': '#22c55e', '33': '#eab308',
    '34': '#3b82f6', '35': '#d946ef', '36': '#06b6d4', '37': '#e5e7eb',
    '90': '#9ca3af', '91': '#f87171', '92': '#4ade80', '93': '#facc15',
    '94': '#60a5fa', '95': '#e879f9', '96': '#22d3ee', '97': '#f3f4f6',
  }

  const parts: { text: string; color?: string }[] = []
  // eslint-disable-next-line no-control-regex
  const regex = /\x1B\[([0-9;]+)m/g
  let lastIdx = 0
  let currentColor: string | undefined

  let match
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push({ text: text.slice(lastIdx, match.index), color: currentColor })
    }
    const codes = match[1].split(';')
    const colorCode = codes.find(c => ansiColors[c])
    if (codes.includes('0')) currentColor = undefined
    else if (colorCode) currentColor = ansiColors[colorCode]
    lastIdx = match.index + match[0].length
  }
  if (lastIdx < text.length) {
    parts.push({ text: text.slice(lastIdx), color: currentColor })
  }

  return (
    <>
      {parts.map((p, i) =>
        p.color
          ? <span key={i} style={{ color: p.color }}>{p.text}</span>
          : <span key={i}>{p.text}</span>
      )}
    </>
  )
}

function stripAnsi(text: string): string {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1B\[[0-9;]*m/g, '')
}

function stripPrefixes(line: string): string {
  return line
    .replace(/^\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[,.\d]*\s*-\s*/, '')
    .replace(/^(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*-\s*/, '')
    .replace(/^\S+\s*-\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*-\s*/, '')
    .trim()
}

const NOISE_PATTERNS = [
  /chromedriver/i,
  /uc_driver/i,
  /download\s*complete/i,
  /extracting/i,
  /\bunzip\b/i,
  /saved\s*to:/i,
  /\bexecutable\b/i,
  /ready\s*for\s*use/i,
]

function filterLogs(rawLogs: string): string {
  const lines = rawLogs.split('\n')
  const filtered: string[] = []
  let prevKey = ''

  for (const line of lines) {
    const plain = stripAnsi(line).trim()

    if (!plain || /^\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[,.\d]*\s*-\s*-?\s*$/.test(plain)) {
      continue
    }
    if (/^[\s\-]+$/.test(plain)) {
      continue
    }

    if (NOISE_PATTERNS.some(p => p.test(plain))) {
      continue
    }

    const key = stripPrefixes(plain)
    if (key && key === prevKey) {
      continue
    }
    prevKey = key

    filtered.push(line)
  }

  return filtered.join('\n')
}

export default function JobsPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list({ per_page: 50 }).then(r => r.data),
    refetchInterval: 5000,
  })

  const { messages } = useWebSocket()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Jobs</h2>
        <p className="text-sm text-muted-foreground mt-0.5">Track vendor check and submission operations</p>
      </div>

      {messages.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          Live updates active
        </div>
      )}

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground bg-[hsl(var(--table-header,var(--secondary)))]">
              <th className="px-4 py-2.5 text-left font-medium w-8"></th>
              <th className="px-4 py-2.5 text-left font-medium">Job ID</th>
              <th className="px-4 py-2.5 text-left font-medium">Domain</th>
              <th className="px-4 py-2.5 text-left font-medium">Action</th>
              <th className="px-4 py-2.5 text-left font-medium">Vendor</th>
              <th className="px-4 py-2.5 text-left font-medium">Status</th>
              <th className="px-4 py-2.5 text-left font-medium">Progress</th>
              <th className="px-4 py-2.5 text-left font-medium">Requested</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.map((job: any) => {
              const progress = job.progress || {}
              const entries = Object.entries(progress)
              const total = entries.length
              const done = entries.filter(([, s]: any) => s === 'success' || s === 'failed').length
              const allDone = total > 0 && done === total
              const displayStatus = allDone ? 'completed' : job.status
              const isExpanded = expandedId === job.id

              return (
                <JobRow
                  key={job.id}
                  job={job}
                  displayStatus={displayStatus}
                  domainName={job.domain_name || job.domain_id.slice(0, 8) + '...'}
                  total={total}
                  done={done}
                  allDone={allDone}
                  entries={entries}
                  expanded={isExpanded}
                  onToggle={() => setExpandedId(prev => prev === job.id ? null : job.id)}
                />
              )
            })}
            {isLoading && (
              <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                <Loader2 size={16} className="animate-spin inline mr-2" />Loading...
              </td></tr>
            )}
            {!isLoading && (!data?.items || data.items.length === 0) && (
              <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                No jobs yet. Trigger a check from the Domains page.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return '--'
  const start = new Date(startedAt).getTime()
  const end = completedAt ? new Date(completedAt).getTime() : Date.now()
  const secs = Math.round((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const remSecs = secs % 60
  return `${mins}m ${remSecs}s`
}

function JobRow({ job, displayStatus, domainName, total, done, allDone, entries, expanded, onToggle }: {
  job: any; displayStatus: string; domainName: string; total: number; done: number; allDone: boolean
  entries: [string, unknown][]; expanded: boolean; onToggle: () => void
}) {
  const [selectedVendor, setSelectedVendor] = useState<string | null>(null)

  const { data: vendorResults } = useQuery({
    queryKey: ['domain-results', job.domain_id],
    queryFn: () => domainsApi.results(job.domain_id).then(r => r.data),
    enabled: expanded,
  })

  const { data: vendors } = useQuery({
    queryKey: ['vendors'],
    queryFn: () => vendorsApi.list().then(r => r.data),
    staleTime: 60000,
    enabled: expanded,
  })

  const vendorLookup: Record<string, any> = {}
  vendors?.forEach((v: any) => { vendorLookup[v.name] = v })

  // Filter by action_type to avoid showing logs from a different action (e.g. submit vs check)
  const logsMap: Record<string, { logs: string; duration: number; status: string; category?: string; error?: string }> = {}
  vendorResults
    ?.filter((r: any) => r.action_type === job.action_type)
    .forEach((r: any) => {
      const v = vendors?.find((v: any) => v.id === r.vendor_id)
      if (v) {
        logsMap[v.name] = {
          logs: r.raw_response?.logs || r.raw_response?.raw_log || '',
          duration: r.raw_response?.duration_seconds || 0,
          status: r.status,
          category: r.category,
          error: r.error_message,
        }
      }
    })

  const duration = formatDuration(job.started_at, job.completed_at)

  return (
    <>
      <tr className="border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors cursor-pointer"
        onClick={onToggle}>
        <td className="px-4 py-2.5 text-muted-foreground">
          {entries.length > 0 && (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
        </td>
        <td className="px-4 py-2.5">
          <span className="font-mono text-[10px] text-muted-foreground/70">{job.id.slice(0, 8)}</span>
        </td>
        <td className="px-4 py-2.5">
          <span className="font-medium text-primary/90 dark:text-[hsl(265,50%,72%)]">{domainName}</span>
        </td>
        <td className="px-4 py-2.5 capitalize">{job.action_type}</td>
        <td className="px-4 py-2.5">{job.vendor_filter || 'All'}</td>
        <td className="px-4 py-2.5"><StatusBadge status={displayStatus} /></td>
        <td className="px-4 py-2.5">
          {total > 0 ? (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden max-w-[120px]">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${allDone ? 'bg-emerald-500' : 'bg-sky-500'}`}
                  style={{ width: `${(done / total) * 100}%` }}
                />
              </div>
              <span className="text-[11px] text-muted-foreground font-mono">{done}/{total}</span>
            </div>
          ) : (
            <span className="text-[11px] text-muted-foreground">--</span>
          )}
        </td>
        <td className="px-4 py-2.5">
          <div className="text-[11px] text-muted-foreground">{new Date(job.requested_at).toLocaleString()}</div>
          <div className="text-[10px] text-muted-foreground/50 mt-0.5">Duration: {duration}</div>
        </td>
      </tr>

      {expanded && entries.length > 0 && (
        <tr>
          <td colSpan={8} className="px-0 py-0">
            <div className="bg-[hsl(var(--table-header,var(--secondary)))] border-t border-border">
              <div className="flex flex-wrap gap-1 px-4 pt-3 pb-2 border-b border-border">
                {entries.map(([vendor, status]: any) => (
                  <button
                    key={vendor}
                    onClick={() => setSelectedVendor(prev => prev === vendor ? null : vendor)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      selectedVendor === vendor
                        ? 'bg-primary/15 text-primary'
                        : 'bg-card border border-border hover:bg-accent text-muted-foreground'
                    }`}
                  >
                    <span>{vendor}</span>
                    <StatusBadge status={status} />
                    {logsMap[vendor]?.duration > 0 && (
                      <span className="text-[9px] text-muted-foreground/50">{logsMap[vendor].duration}s</span>
                    )}
                  </button>
                ))}
              </div>

              {selectedVendor && logsMap[selectedVendor] && (
                <div className="px-4 py-3">
                  {logsMap[selectedVendor].category && (
                    <div className="text-xs mb-2">Result: <span className="font-medium text-emerald-400">{logsMap[selectedVendor].category}</span></div>
                  )}
                  {logsMap[selectedVendor].error && (
                    <div className="text-xs text-red-400 mb-2 max-h-20 overflow-y-auto font-mono whitespace-pre-wrap">{logsMap[selectedVendor].error}</div>
                  )}
                  <div className="bg-[hsl(260,22%,6%)] rounded-md border border-border p-3 overflow-y-auto resize-y" style={{ minHeight: '6rem', height: '20rem', maxHeight: '80vh' }}>
                    <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap leading-relaxed">
                      <AnsiLog text={filterLogs(logsMap[selectedVendor].logs)} />
                    </pre>
                  </div>
                </div>
              )}

              {!selectedVendor && (
                <div className="px-4 py-4 text-xs text-muted-foreground/50 text-center">
                  Click a vendor above to view its classifier logs
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
