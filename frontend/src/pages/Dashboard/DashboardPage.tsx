import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { dashboardApi } from '@/api/client'
import { useWebSocket } from '@/context/WebSocketContext'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { RefreshCw, ArrowRight, CheckCircle2, MinusCircle, AlertCircle } from 'lucide-react'
import StatsBento from './StatsBento'

type Bucket = 'match' | 'neutral' | 'suspicious' | 'unchecked'

const RISK_KEYWORDS = [
  'suspicious', 'phishing', 'malware', 'malicious', 'spam', 'scam', 'fraud',
  'botnet', 'exploit', 'compromised', 'hacked', 'c2', 'attack', 'trojan',
  'high risk', 'critical risk',
]

const NEUTRAL_KEYWORDS = [
  'not found', 'not rated', 'uncategorized', 'newly registered',
  'newly observed', 'no established', 'unknown', 'unrated', 'inactive sites',
  'untested', 'n/a',
]

function bucketCategoryCell(category: string | null, desired: string | null): Bucket {
  if (!category) return 'unchecked'
  const lower = category.toLowerCase()

  if (RISK_KEYWORDS.some(k => lower.includes(k))) return 'suspicious'

  if (desired) {
    const desiredLower = desired.toLowerCase()
    if (lower.includes(desiredLower)) return 'match'
  }

  if (NEUTRAL_KEYWORDS.some(k => lower.includes(k))) return 'neutral'

  return 'neutral'
}

function bucketReputationCell(reputation: string | null, category: string | null): Bucket {
  // Classify by prefix only to avoid false positives from phrases appearing in aggregate strings
  const value = (reputation || category || '').trim().toLowerCase()
  if (!value) return 'unchecked'
  if (value.startsWith('error')) return 'unchecked'
  if (value.startsWith('clean') || value.startsWith('harmless')) return 'match'
  if (value.startsWith('malicious')) return 'suspicious'
  if (value.startsWith('suspicious')) return 'suspicious'
  return 'neutral'
}

function DomainStatsCard({ row }: { row: any }) {
  const desired = row.domain.desired_category as string | null
  const cells = row.results || []

  const categoryCells = cells.filter((c: any) => c.vendor_type === 'category')
  const reputationCells = cells.filter((c: any) => c.vendor_type === 'reputation')

  let match = 0
  let neutral = 0
  let suspicious = 0
  let unchecked = 0
  for (const cell of categoryCells) {
    if (cell.status !== 'success') { unchecked++; continue }
    const b = bucketCategoryCell(cell.category, desired)
    if (b === 'match') match++
    else if (b === 'suspicious') suspicious++
    else neutral++
  }
  const categoryTotal = categoryCells.length

  let safetyClean = 0
  let safetyMalicious = 0
  let safetyNeutral = 0
  let safetyFailed = 0
  let safetyPending = 0
  for (const cell of reputationCells) {
    if (cell.status === 'failed') { safetyFailed++; continue }
    if (cell.status !== 'success') { safetyPending++; continue }
    const b = bucketReputationCell(cell.reputation, cell.category)
    if (b === 'match') safetyClean++
    else if (b === 'suspicious') safetyMalicious++
    else safetyNeutral++
  }
  const safetyTotal = reputationCells.length

  return (
    <div className="rounded-lg border border-border bg-card p-4 hover:border-primary/40 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0 flex-1">
          <Link
            to={`/domains/${row.domain.id}`}
            className="font-medium text-sm text-primary/90 dark:text-[hsl(265,50%,72%)] hover:underline truncate block"
          >
            {row.domain.domain}
          </Link>
          {desired ? (
            <div className="mt-1">
              <span className="px-1.5 py-px rounded text-[10px] font-medium bg-primary/10 text-primary/70 dark:text-[hsl(265,40%,65%)]">
                {desired}
              </span>
            </div>
          ) : (
            <div className="mt-1 text-[10px] text-muted-foreground/50 italic">No desired category</div>
          )}
          {safetyTotal > 0 && (
            <div className="mt-1.5 text-[10px] text-muted-foreground/80 flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
              <span className="font-medium text-muted-foreground/60">Safety:</span>
              <span className="text-emerald-500">{safetyClean}/{safetyTotal} clean</span>
              {safetyMalicious > 0 && <span className="text-red-500">· {safetyMalicious}/{safetyTotal} malicious</span>}
              {safetyNeutral > 0 && <span className="text-slate-400">· {safetyNeutral}/{safetyTotal} neutral</span>}
              {safetyFailed > 0 && <span className="text-red-400/70">· {safetyFailed}/{safetyTotal} failed</span>}
              {safetyPending > 0 && <span className="text-sky-400/70">· {safetyPending}/{safetyTotal} pending</span>}
            </div>
          )}
        </div>
        <Link
          to={`/domains/${row.domain.id}`}
          className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-primary px-2 py-1 rounded border border-border hover:border-primary/40 transition-colors whitespace-nowrap"
          title="View full vendor breakdown"
        >
          View Details
          <ArrowRight size={10} />
        </Link>
      </div>

      <div className="text-[10px] font-medium text-muted-foreground/60 mb-1.5">Category:</div>

      {categoryTotal > 0 && (
        <div className="h-1.5 w-full rounded-full overflow-hidden flex bg-muted/30 mb-2">
          {match > 0 && <div className="bg-emerald-500" style={{ width: `${(match / categoryTotal) * 100}%` }} />}
          {neutral > 0 && <div className="bg-slate-400" style={{ width: `${(neutral / categoryTotal) * 100}%` }} />}
          {suspicious > 0 && <div className="bg-red-500" style={{ width: `${(suspicious / categoryTotal) * 100}%` }} />}
        </div>
      )}

      <div className="grid grid-cols-3 gap-1.5 text-[10px]">
        <div className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/10 border border-emerald-500/20" title="Category vendors reporting the desired/correct category">
          <CheckCircle2 size={11} className="text-emerald-500 shrink-0" />
          <span className="text-emerald-500 font-semibold">{match}</span>
          <span className="text-muted-foreground/70 truncate">matching</span>
        </div>
        <div className="flex items-center gap-1 px-2 py-1 rounded bg-slate-500/10 border border-slate-500/20" title="Uncategorized / newly registered / unrelated">
          <MinusCircle size={11} className="text-slate-400 shrink-0" />
          <span className="text-slate-400 font-semibold">{neutral}</span>
          <span className="text-muted-foreground/70 truncate">neutral</span>
        </div>
        <div className="flex items-center gap-1 px-2 py-1 rounded bg-red-500/10 border border-red-500/20" title="Flagged as suspicious / malicious / phishing / high-risk">
          <AlertCircle size={11} className="text-red-500 shrink-0" />
          <span className="text-red-500 font-semibold">{suspicious}</span>
          <span className="text-muted-foreground/70 truncate">risky</span>
        </div>
      </div>

      {unchecked > 0 && (
        <div className="mt-2 text-[10px] text-muted-foreground/60">
          {match + neutral + suspicious}/{categoryTotal} category vendors checked · {unchecked} pending
        </div>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const { data: summary } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => dashboardApi.summary().then(r => r.data),
    refetchInterval: 10000,
  })

  const { data: matrix } = useQuery({
    queryKey: ['dashboard-matrix'],
    queryFn: () => dashboardApi.matrix().then(r => r.data),
    refetchInterval: 15000,
  })

  const { messages } = useWebSocket()

  const rows = matrix?.items || []

  return (
    <div className="space-y-10">
      {/* Asymmetric editorial header — left-aligned title with right-side meta + CTA */}
      <header className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between md:gap-12">
        <div className="max-w-[34rem]">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70 mb-2">
            Overview · Live
          </p>
          <h2 className="text-4xl md:text-5xl font-semibold tracking-tighter leading-[0.95]">
            Domain
            <span className="text-muted-foreground/40"> classification</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-3 leading-relaxed">
            Per-domain summary across every reputation and category vendor. Auto-refreshes every 10s.
          </p>
        </div>
        <Link
          to="/domains"
          className="group inline-flex items-center gap-2 self-start md:self-auto px-4 py-2.5 rounded-xl border border-white/10 hover:border-primary/40 bg-white/[0.02] hover:bg-primary/[0.06] transition-colors text-sm font-medium"
        >
          All domains
          <ArrowRight size={14} className="transition-transform duration-300 group-hover:translate-x-0.5" />
        </Link>
      </header>

      <StatsBento
        activeDomains={summary?.active_domains}
        totalVendors={summary?.total_vendors}
        mismatches={summary?.domains_with_mismatches}
        pendingJobs={summary?.pending_jobs}
      />

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border bg-[hsl(var(--table-header,var(--secondary)))] flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Domain Classification Summary
          </h3>
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <RefreshCw size={12} className={messages.length > 0 ? 'animate-spin text-primary' : ''} />
            Auto-refreshing
          </div>
        </div>
        <div className="p-4">
          {rows.length === 0 ? (
            <div className="px-5 py-12 text-center text-muted-foreground text-sm">
              No domains added yet. Go to <Link to="/domains" className="text-primary hover:underline">Domains</Link> to add your first domain.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {rows.map((row: any) => <DomainStatsCard key={row.domain.id} row={row} />)}
            </div>
          )}
        </div>
      </div>

      {messages.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="p-4 border-b border-border">
            <h3 className="font-semibold">Live Activity</h3>
          </div>
          <div className="divide-y divide-border max-h-64 overflow-y-auto">
            {messages.slice(0, 10).map((msg, i) => (
              <div key={i} className="px-4 py-3 flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <StatusBadge status={msg.status} />
                  <span className="font-medium">{msg.vendor}</span>
                  {msg.category && <CategoryBadge category={msg.category} />}
                </div>
                <span className="text-xs text-muted-foreground">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
