import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { domainsApi, jobsApi, vendorsApi } from '@/api/client'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { Plus, Search, Trash2, X, Loader2, PlayCircle, SendHorizonal, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'
import { CATEGORIES, HIDDEN_VENDORS, getManualUrl } from '@/lib/constants'
import { Link } from 'react-router-dom'

function reputationString(r: any): string {
  return r?.reputation || r?.category || ''
}

function extractDetail(raw: string): string | null {
  const m = raw.match(/\(([^)]+)\)/)
  return m ? m[1] : null
}

function deriveBadgeStatus(r: any): string | null | undefined {
  if (!r) return undefined
  if (r.status !== 'success') return r.status
  const value = reputationString(r).toLowerCase()
  if (value.startsWith('error')) return 'error'
  if (value.startsWith('malicious')) return 'malicious'
  if (value.startsWith('suspicious')) return 'suspicious'
  return 'clean'
}

function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

const SAFETY_DEFAULT_W = (i: number) => (i === 0 ? 230 : 200)
const CAT_DEFAULT_W    = (i: number) => (i === 0 ? 250 : 200)

function useResizableColumns(count: number, defaultW: (i: number) => number) {
  const [widths, setWidths] = useState<number[]>(() =>
    Array.from({ length: count }, (_, i) => defaultW(i))
  )
  const colRefs   = useRef<(HTMLTableColElement | null)[]>([])
  const liveW     = useRef<number[]>([])

  useEffect(() => { liveW.current = [...widths] }, [widths])

  useEffect(() => {
    setWidths(prev => {
      if (prev.length === count) return prev
      return Array.from({ length: count }, (_, i) => prev[i] ?? defaultW(i))
    })
  // defaultW is module-level constant — safe to omit from deps
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count])

  const startResize = useCallback((idx: number, e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = liveW.current[idx] ?? defaultW(idx)

    document.body.style.cursor    = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMove = (ev: MouseEvent) => {
      const newW = Math.max(80, startW + ev.clientX - startX)
      liveW.current[idx] = newW
      const col = colRefs.current[idx]
      if (col) col.style.width = `${newW}px`
    }

    const onUp = () => {
      document.body.style.cursor    = ''
      document.body.style.userSelect = ''
      setWidths([...liveW.current])
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup',   onUp)
    }

    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup',   onUp)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { widths, colRefs, startResize }
}

function ResizeHandle({ onMouseDown }: { onMouseDown: (e: React.MouseEvent) => void }) {
  return (
    <div
      onMouseDown={onMouseDown}
      onClick={e => e.stopPropagation()}
      className="absolute right-0 top-0 h-full w-[6px] cursor-col-resize z-20 group/rh flex items-center justify-center"
    >
      <div className="w-[2px] h-[55%] rounded-full bg-transparent group-hover/rh:bg-border transition-colors duration-150" />
    </div>
  )
}

export default function DomainsPage() {
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [domainToDelete, setDomainToDelete] = useState<any>(null)
  const [bulkSafetyPending, setBulkSafetyPending] = useState(false)
  const [bulkCatPending, setBulkCatPending] = useState(false)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['domains', search],
    queryFn: () => domainsApi.list({ search, per_page: 50 }).then(r => r.data),
  })

  const { data: vendors } = useQuery({
    queryKey: ['vendors'],
    queryFn: () => vendorsApi.list().then(r => r.data),
    staleTime: 60000,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => domainsApi.delete(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['domains'] }); toast.success('Domain removed') },
    onError: () => toast.error('Failed to delete domain'),
  })

  const bulkReputationMutation = useMutation({
    mutationFn: () => jobsApi.bulkReputation(),
    onMutate: () => { setBulkSafetyPending(true); setTimeout(() => setBulkSafetyPending(false), 15000) },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast.success('Reputation check started for all domains') },
    onError: () => toast.error('Failed to start bulk reputation check'),
  })

  const bulkCheckMutation = useMutation({
    mutationFn: () => jobsApi.bulkCheck(),
    onMutate: () => { setBulkCatPending(true); setTimeout(() => setBulkCatPending(false), 15000) },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast.success('Check started for all domains') },
    onError: () => toast.error('Failed to start bulk check'),
  })

  const bulkSubmitMutation = useMutation({
    mutationFn: () => jobsApi.bulkSubmit(),
    onMutate: () => { setBulkCatPending(true); setTimeout(() => setBulkCatPending(false), 15000) },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast.success('Submit started for all domains') },
    onError: () => toast.error('Failed to start bulk submit'),
  })

  const categoryVendors  = vendors?.filter((v: any) => v.vendor_type === 'category'   && !HIDDEN_VENDORS.has(v.name)) || []
  const reputationVendors = vendors?.filter((v: any) => v.vendor_type === 'reputation' && !HIDDEN_VENDORS.has(v.name)) || []

  const { widths: safetyW, colRefs: safetyColRefs, startResize: startSafetyResize } =
    useResizableColumns(1 + reputationVendors.length, SAFETY_DEFAULT_W)
  const { widths: catW, colRefs: catColRefs, startResize: startCatResize } =
    useResizableColumns(1 + categoryVendors.length, CAT_DEFAULT_W)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Domain Categorization & Safety</h2>
          <p className="text-sm text-muted-foreground mt-0.5">Threat reputation and web proxy categorization across security vendors</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:brightness-110 transition-all"
          >
            <Plus size={14} /> Add Domain
          </button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search domains..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 rounded-md border border-input bg-card text-sm focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground/50"
        />
      </div>

      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border bg-[hsl(var(--table-header,var(--secondary)))] flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Safety Status <span className="text-muted-foreground/50 font-normal normal-case">({reputationVendors.length} vendor{reputationVendors.length === 1 ? '' : 's'})</span>
          </h3>
          <button
            onClick={() => bulkReputationMutation.mutate()}
            disabled={bulkReputationMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-[11px] font-medium hover:bg-accent transition-colors disabled:opacity-50"
          >
            {bulkReputationMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <PlayCircle size={12} />}
            Verify All Domains
          </button>
        </div>
        <div className="overflow-auto" style={{ maxHeight: '60vh' }}>
          <table className="text-sm" style={{ tableLayout: 'fixed', minWidth: `${safetyW.reduce((a, b) => a + b, 0)}px` }}>
            <colgroup>
              {safetyW.map((w, i) => (
                <col key={i} ref={el => { safetyColRefs.current[i] = el }} style={{ width: `${w}px` }} />
              ))}
            </colgroup>
            <thead className="sticky top-0 z-20 bg-card">
              <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground select-none">
                <th className="relative px-4 py-2.5 text-left font-medium sticky left-0 bg-card z-30 overflow-hidden">
                  <span className="block truncate">Domain</span>
                  <ResizeHandle onMouseDown={e => startSafetyResize(0, e)} />
                </th>
                {reputationVendors.map((v: any, i: number) => {
                  const vendorUrl = getManualUrl(v.name, 'check', '')?.replace(encodeURIComponent(''), '').replace(/[?&].*$/, '') || null
                  return (
                    <th key={v.id} className="relative px-2 py-2.5 text-center font-medium border-l border-border/40 overflow-hidden">
                      {vendorUrl ? (
                        <a href={vendorUrl} target="_blank" rel="noopener noreferrer" className="block truncate hover:text-primary transition-colors" title={`Open ${v.display_name}`}>
                          {v.display_name}
                        </a>
                      ) : (
                        <span className="block truncate">{v.display_name}</span>
                      )}
                      <ResizeHandle onMouseDown={e => startSafetyResize(1 + i, e)} />
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {data?.items?.map((domain: any) => (
                <SafetyRow key={domain.id} domain={domain} reputationVendors={reputationVendors} bulkPending={bulkSafetyPending} onDelete={() => setDomainToDelete(domain)} />
              ))}
              {isLoading && <LoadingRow cols={1 + reputationVendors.length} />}
              {!isLoading && (!data?.items || data.items.length === 0) && (
                <EmptyRow cols={1 + reputationVendors.length} text="No domains yet" />
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border bg-[hsl(var(--table-header,var(--secondary)))] flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Web Proxy Categorization <span className="text-muted-foreground/50 font-normal normal-case">({categoryVendors.length} vendor{categoryVendors.length === 1 ? '' : 's'})</span>
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => bulkCheckMutation.mutate()}
              disabled={bulkCheckMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-[11px] font-medium hover:bg-accent transition-colors disabled:opacity-50"
            >
              {bulkCheckMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <PlayCircle size={12} />}
              Check All Domains
            </button>
            <button
              onClick={() => bulkSubmitMutation.mutate()}
              disabled={bulkSubmitMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary/15 text-primary text-[11px] font-medium hover:bg-primary/25 transition-colors disabled:opacity-50"
            >
              {bulkSubmitMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <SendHorizonal size={12} />}
              Submit All Domains
            </button>
          </div>
        </div>
        <div className="overflow-auto" style={{ maxHeight: '60vh' }}>
          <table className="text-sm" style={{ tableLayout: 'fixed', minWidth: `${catW.reduce((a, b) => a + b, 0)}px` }}>
            <colgroup>
              {catW.map((w, i) => (
                <col key={i} ref={el => { catColRefs.current[i] = el }} style={{ width: `${w}px` }} />
              ))}
            </colgroup>
            <thead className="sticky top-0 z-20 bg-card">
              <VendorHeaders categoryVendors={categoryVendors} widths={catW} startResize={startCatResize} />
            </thead>
            <tbody>
              {data?.items?.map((domain: any) => (
                <CategorizationRow
                  key={domain.id}
                  domain={domain}
                  categoryVendors={categoryVendors}
                  bulkPending={bulkCatPending}
                  onDelete={() => setDomainToDelete(domain)}
                />
              ))}
              {isLoading && <LoadingRow cols={1 + categoryVendors.length} />}
              {!isLoading && (!data?.items || data.items.length === 0) && (
                <EmptyRow cols={1 + categoryVendors.length} text="No domains yet. Click &quot;Add Domain&quot; to get started." />
              )}
            </tbody>
          </table>
        </div>
      </section>

      {showAdd && <AddDomainModal onClose={() => setShowAdd(false)} />}

      {domainToDelete && (
        <DeleteConfirmDialog
          domain={domainToDelete}
          onConfirm={() => {
            deleteMutation.mutate(domainToDelete.id)
            setDomainToDelete(null)
          }}
          onCancel={() => setDomainToDelete(null)}
        />
      )}
    </div>
  )
}

function VendorHeaders({ categoryVendors, widths, startResize }: {
  categoryVendors: any[]
  widths: number[]
  startResize: (idx: number, e: React.MouseEvent) => void
}) {
  return (
    <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground select-none">
      <th className="relative px-4 py-2.5 text-left font-medium sticky left-0 bg-card z-30 overflow-hidden">
        <span className="block truncate">Domain</span>
        <ResizeHandle onMouseDown={e => startResize(0, e)} />
      </th>
      {categoryVendors.map((v: any, i: number) => {
        const vendorUrl = getManualUrl(v.name, 'check', '')?.replace(encodeURIComponent(''), '').replace(/[?&].*$/, '') || null
        return (
          <th key={v.id} className="relative px-4 py-2.5 text-center font-medium overflow-hidden">
            {vendorUrl ? (
              <a href={vendorUrl} target="_blank" rel="noopener noreferrer" className="block truncate hover:text-primary transition-colors" title={`Open ${v.display_name}`}>
                {v.display_name}
              </a>
            ) : (
              <span className="block truncate">{v.display_name}</span>
            )}
            <ResizeHandle onMouseDown={e => startResize(1 + i, e)} />
          </th>
        )
      })}
    </tr>
  )
}

function LoadingRow({ cols }: { cols: number }) {
  return <tr><td colSpan={cols} className="px-5 py-10 text-center text-muted-foreground text-sm"><Loader2 size={18} className="animate-spin inline mr-2 text-primary/50" />Loading domains...</td></tr>
}
function EmptyRow({ cols, text }: { cols: number; text: string }) {
  return (
    <tr><td colSpan={cols} className="px-5 py-12 text-center">
      <div className="flex flex-col items-center gap-2">
        <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
          <Search size={18} className="text-muted-foreground/50" />
        </div>
        <p className="text-sm text-muted-foreground">{text}</p>
      </div>
    </td></tr>
  )
}

function SafetyRow({ domain, reputationVendors, bulkPending, onDelete }: { domain: any; reputationVendors: any[]; bulkPending?: boolean; onDelete: () => void }) {
  const queryClient = useQueryClient()

  const { data: results } = useQuery({
    queryKey: ['domain-results', domain.id],
    queryFn: () => domainsApi.results(domain.id).then(r => r.data),
    refetchInterval: 2000,
  })

  const resultMap: Record<number, any> = {}
  results?.filter((r: any) => r.action_type === 'reputation').forEach((r: any) => { resultMap[r.vendor_id] = r })

  const [pendingVendors, setPendingVendors] = useState<Set<string>>(new Set())
  const markPending = (vendor: string) => {
    setPendingVendors(prev => { const n = new Set(prev); n.add(vendor); return n })
    setTimeout(() => setPendingVendors(prev => { const n = new Set(prev); n.delete(vendor); return n }), 15000)
  }

  const checkMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.reputation({ domain_id: domain.id, vendor }),
    onMutate: (vendor) => { markPending(vendor); toast(`Verifying ${vendor}...`, { icon: '🔍' }) },
    onError: (_, vendor) => toast.error(`Verification failed for ${vendor}`),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }),
  })

  const verifyAllMutation = useMutation({
    mutationFn: () => jobsApi.reputation({ domain_id: domain.id }),
    onMutate: () => {
      reputationVendors.forEach((v: any) => markPending(v.name))
      toast('Verifying all reputation vendors...', { icon: '🔍' })
    },
    onError: () => toast.error('Verify all failed'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }),
  })

  const cancelMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.cancelVendor(domain.id, vendor),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }); toast.success('Cancelled') },
    onError: () => toast.error('Cancel failed'),
  })

  const anyBusy = bulkPending || reputationVendors.some((v: any) => {
    const r = resultMap[v.id]
    return r?.status === 'running' || r?.status === 'pending' || pendingVendors.has(v.name)
  })

  return (
    <tr className="group/row border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors">
      <td className="px-4 py-3 align-middle sticky left-0 bg-card z-10">
        <div className="flex items-center justify-between gap-1.5">
          <Link
            to={`/domains/${domain.id}`}
            className="font-medium text-primary/90 dark:text-[hsl(265,50%,72%)] hover:underline truncate"
          >
            {domain.domain}
          </Link>
          {anyBusy ? (
            <Loader2 size={13} className="animate-spin text-sky-400 flex-shrink-0" />
          ) : (
            <div className="flex items-center gap-0.5 opacity-0 group-hover/row:opacity-100 transition-opacity flex-shrink-0">
              <button
                onClick={() => verifyAllMutation.mutate()}
                className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                title="Verify all"
              >
                <PlayCircle size={13} />
              </button>
              <button
                onClick={onDelete}
                className="p-1 rounded hover:bg-destructive/15 text-muted-foreground/30 hover:text-destructive transition-colors"
                title="Delete"
              >
                <Trash2 size={12} />
              </button>
            </div>
          )}
        </div>
      </td>
      {reputationVendors.map((v: any) => {
        const r = resultMap[v.id]
        const busy = r?.status === 'running' || r?.status === 'pending' || pendingVendors.has(v.name) || bulkPending
        const lastFailed = r?.status === 'failed'
        const manualUrl = lastFailed ? getManualUrl(v.name, 'check', domain.domain) : null
        const hasResult = r?.status && r.status !== 'running' && r.status !== 'pending'
        const repString = reputationString(r)
        const detail = !busy && r?.status === 'success' && repString ? extractDetail(repString) : null
        const badgeStatus = deriveBadgeStatus(r)
        return (
          <td key={v.id} className="px-2 py-3 align-top border-l border-border/40">
            <div className="flex flex-col items-center gap-1.5">
              <StatusBadge
                status={busy ? undefined : badgeStatus}
                loading={busy}
                onCancel={busy ? () => cancelMutation.mutate(v.name) : undefined}
              />
              {detail && !busy && (
                <span className="text-[10px] text-muted-foreground/80 font-mono break-all text-center" title={repString}>
                  {detail}
                </span>
              )}
              {r?.completed_at && !busy && (
                <span className="text-[9px] text-muted-foreground/50">{timeAgo(r.completed_at)}</span>
              )}
              {!busy && (
                <button
                  onClick={() => checkMutation.mutate(v.name)}
                  className="px-2.5 h-[24px] rounded-md text-[11px] font-medium transition-all duration-200 bg-secondary hover:bg-accent text-secondary-foreground hover:text-accent-foreground whitespace-nowrap"
                >
                  {hasResult ? 'Re-verify' : 'Verify'}
                </button>
              )}
              {manualUrl && !busy && (
                <a
                  href={manualUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Automated check failed — open vendor page to verify manually"
                  className="inline-flex items-center gap-1 px-2 h-[20px] rounded-md text-[9px] font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 border border-amber-500/30 transition-colors"
                >
                  <ExternalLink size={9} />
                  Manual
                </a>
              )}
            </div>
          </td>
        )
      })}
    </tr>
  )
}

function CategorizationRow({ domain, categoryVendors, bulkPending, onDelete }: {
  domain: any; categoryVendors: any[]; bulkPending?: boolean; onDelete: () => void
}) {
  const queryClient = useQueryClient()

  const { data: results } = useQuery({
    queryKey: ['domain-results', domain.id],
    queryFn: () => domainsApi.results(domain.id).then(r => r.data),
    refetchInterval: 2000,
  })

  const [pendingCheck, setPendingCheck] = useState<Set<string>>(new Set())
  const [pendingSubmit, setPendingSubmit] = useState<Set<string>>(new Set())
  const markCheckPending = (vendor: string) => {
    if (vendor === '__all__') {
      categoryVendors.forEach((v: any) => markCheckPending(v.name))
      return
    }
    setPendingCheck(prev => { const n = new Set(prev); n.add(vendor); return n })
    setTimeout(() => setPendingCheck(prev => { const n = new Set(prev); n.delete(vendor); return n }), 15000)
  }
  const markSubmitPending = (vendor: string) => {
    if (vendor === '__all__') {
      categoryVendors.forEach((v: any) => markSubmitPending(v.name))
      return
    }
    setPendingSubmit(prev => { const n = new Set(prev); n.add(vendor); return n })
    setTimeout(() => setPendingSubmit(prev => { const n = new Set(prev); n.delete(vendor); return n }), 15000)
  }

  const checkVendorMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.check({
      domain_id: domain.id,
      vendor: vendor === '__all__' ? undefined : vendor,
    }),
    onMutate: (vendor) => {
      markCheckPending(vendor)
      if (vendor === '__all__') toast('Checking all vendors...', { icon: '🔄' })
      else toast(`Checking ${vendor}...`, { icon: '🔄' })
    },
    onError: (_, vendor) => toast.error(`Check failed${vendor !== '__all__' ? ` for ${vendor}` : ''}`),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }),
  })

  const submitVendorMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.submit({
      domain_id: domain.id,
      vendor: vendor === '__all__' ? undefined : vendor,
    }),
    onMutate: (vendor) => {
      markSubmitPending(vendor)
      if (vendor === '__all__') toast('Submitting to all vendors...', { icon: '📤' })
      else toast(`Submitting to ${vendor}...`, { icon: '📤' })
    },
    onError: (_, vendor) => toast.error(`Submit failed${vendor !== '__all__' ? ` for ${vendor}` : ''}`),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }),
  })

  const cancelMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.cancelVendor(domain.id, vendor),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }); toast.success('Cancelled') },
    onError: () => toast.error('Cancel failed'),
  })

  const resultMap: Record<number, any> = {}
  results?.filter((r: any) => r.action_type === 'check').forEach((r: any) => { resultMap[r.vendor_id] = r })
  const submitResultMap: Record<number, any> = {}
  results?.filter((r: any) => r.action_type === 'submit').forEach((r: any) => { submitResultMap[r.vendor_id] = r })

  const anyBusy = bulkPending || categoryVendors.some((v: any) => {
    const r = resultMap[v.id]
    const sr = submitResultMap[v.id]
    return r?.status === 'running' || r?.status === 'pending' || pendingCheck.has(v.name)
      || sr?.status === 'running' || sr?.status === 'pending' || pendingSubmit.has(v.name)
  })

  return (
    <>
      <tr className="group/row border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors">
        <td className="px-4 py-2.5 sticky left-0 bg-card z-10">
          <div className="flex items-start justify-between gap-1.5">
            <div className="min-w-0">
              <Link
                to={`/domains/${domain.id}`}
                className="font-medium text-primary/90 dark:text-[hsl(265,50%,72%)] hover:underline block truncate"
              >
                {domain.domain}
              </Link>
              <div className="mt-0.5">
                {domain.desired_category
                  ? <span className="px-1.5 py-px rounded text-[10px] font-medium bg-primary/10 text-primary/70 dark:text-[hsl(265,40%,65%)]">{domain.desired_category}</span>
                  : <span className="text-[10px] text-muted-foreground/40 italic">No category set</span>
                }
              </div>
            </div>
            {anyBusy ? (
              <Loader2 size={13} className="animate-spin text-sky-400 flex-shrink-0 mt-0.5" />
            ) : (
              <div className="flex items-center gap-0.5 opacity-0 group-hover/row:opacity-100 transition-opacity flex-shrink-0 mt-0.5">
                <button
                  onClick={() => checkVendorMutation.mutate('__all__')}
                  className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                  title="Check all vendors"
                >
                  <PlayCircle size={13} />
                </button>
                {domain.desired_category && (
                  <button
                    onClick={() => submitVendorMutation.mutate('__all__')}
                    className="p-1 rounded hover:bg-primary/10 text-primary/60 hover:text-primary transition-colors"
                    title="Submit all vendors"
                  >
                    <SendHorizonal size={13} />
                  </button>
                )}
                <button
                  onClick={onDelete}
                  className="p-1 rounded hover:bg-destructive/15 text-muted-foreground/30 hover:text-destructive transition-colors"
                  title="Delete"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            )}
          </div>
        </td>
        {categoryVendors.map((v: any) => {
          const r = resultMap[v.id]
          const sr = submitResultMap[v.id]
          const isCheckBusy = r?.status === 'running' || r?.status === 'pending' || pendingCheck.has(v.name)
          const isSubmitBusy = sr?.status === 'running' || sr?.status === 'pending' || pendingSubmit.has(v.name)
          const checkFailed = r?.status === 'failed'
          const submitFailed = sr?.status === 'failed'
          const manualCheckUrl = checkFailed ? getManualUrl(v.name, 'check', domain.domain) : null
          const manualSubmitUrl = submitFailed && v.supports_submit ? getManualUrl(v.name, 'submit', domain.domain) : null
          return (
            <td key={v.id} className="px-3 py-2 text-center">
              <div className="flex flex-col items-center gap-1">
                {isCheckBusy || isSubmitBusy ? (
                  <StatusBadge status="running" onCancel={() => cancelMutation.mutate(v.name)} />
                ) : r?.status === 'success' ? (
                  <CategoryBadge category={r.category} desired={domain.desired_category} />
                ) : (
                  <StatusBadge status={r?.status} />
                )}
                {r?.completed_at && !isCheckBusy && !isSubmitBusy && (
                  <span className="text-[9px] text-muted-foreground/50">{timeAgo(r.completed_at)}</span>
                )}
                <div className="flex flex-wrap justify-center items-center gap-1 mt-0.5">
                  <button
                    onClick={() => checkVendorMutation.mutate(v.name)}
                    disabled={isCheckBusy}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-200 ${
                      isCheckBusy
                        ? 'bg-muted/40 text-muted-foreground/30 cursor-not-allowed'
                        : 'bg-secondary hover:bg-accent text-secondary-foreground'
                    }`}
                  >
                    {isCheckBusy ? <Loader2 size={9} className="animate-spin" /> : 'Check'}
                  </button>
                  {v.supports_submit && (
                    <button
                      onClick={() => submitVendorMutation.mutate(v.name)}
                      disabled={isSubmitBusy || isCheckBusy || !domain.desired_category}
                      title={!domain.desired_category ? 'Set desired category first' : `Submit ${domain.desired_category} to ${v.display_name}`}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-200 ${
                        isSubmitBusy || isCheckBusy
                          ? 'bg-primary/10 text-primary/30 cursor-not-allowed'
                          : !domain.desired_category
                            ? 'bg-muted/30 text-muted-foreground/30 cursor-not-allowed'
                            : 'bg-primary/15 text-primary hover:bg-primary/25'
                      }`}
                    >
                      {isSubmitBusy ? <Loader2 size={9} className="animate-spin" /> : 'Submit'}
                    </button>
                  )}
                </div>
                {(manualCheckUrl || manualSubmitUrl) && (
                  <div className="flex items-center gap-1 mt-0.5">
                    {manualCheckUrl && (
                      <a
                        href={manualCheckUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Automated check failed — open vendor page to check manually"
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[9px] font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 border border-amber-500/30 transition-colors"
                      >
                        <ExternalLink size={8} />
                        Manual Check
                      </a>
                    )}
                    {manualSubmitUrl && (
                      <a
                        href={manualSubmitUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Automated submit failed — open vendor page to submit manually"
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[9px] font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 border border-amber-500/30 transition-colors"
                      >
                        <ExternalLink size={8} />
                        Manual Submit
                      </a>
                    )}
                  </div>
                )}
              </div>
            </td>
          )
        })}
      </tr>
    </>
  )
}

function DeleteConfirmDialog({ domain, onConfirm, onCancel }: { domain: any; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onCancel}>
      <div className="w-full max-w-sm bg-card rounded-xl border border-border p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-2">Delete Domain</h3>
        <p className="text-sm text-muted-foreground mb-1">
          Are you sure you want to remove this domain?
        </p>
        <p className="text-sm font-medium text-foreground mb-5 px-3 py-2 rounded bg-destructive/10 border border-destructive/20">
          {domain.domain}
        </p>
        <p className="text-xs text-muted-foreground mb-5">
          This will remove the domain and all its check results from the dashboard. The action cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent transition-colors">
            Cancel
          </button>
          <button onClick={onConfirm} className="px-4 py-2 rounded-md bg-destructive text-destructive-foreground text-sm font-medium hover:brightness-110 transition-all">
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

function AddDomainModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<'manual' | 'csv'>('manual')
  const [domain, setDomain] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [category, setCategory] = useState('')
  const [email, setEmail] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [csvParsed, setCsvParsed] = useState<any[]>([])
  const [csvImporting, setCsvImporting] = useState(false)
  const [csvProgress, setCsvProgress] = useState({ done: 0, total: 0, errors: 0 })
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (data: any) => domainsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['domains'] })
      toast.success('Domain added')
      onClose()
    },
    onError: (err: any) => { setError(err.response?.data?.detail || 'Failed to add domain'); toast.error('Failed to add domain') },
  })

  const categories = CATEGORIES

  const downloadTemplate = () => {
    const header = 'domain,display_name,desired_category,email_for_submit,notes'
    const example = 'example.com,My Website,Business,admin@example.com,Main company site'
    const blob = new Blob([header + '\n' + example + '\n'], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'domain_import_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCsvFile = (file: File) => {
    setCsvFile(file)
    setError('')
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      const lines = text.split('\n').map(l => l.trim()).filter(Boolean)
      if (lines.length < 2) { setError('CSV must have a header row and at least one data row'); return }

      const header = lines[0].toLowerCase().split(',').map(h => h.trim())
      const domainIdx = header.indexOf('domain')
      if (domainIdx === -1) { setError('CSV must have a "domain" column'); return }

      const displayIdx = header.indexOf('display_name')
      const catIdx = header.indexOf('desired_category')
      const emailIdx = header.indexOf('email_for_submit')
      const notesIdx = header.indexOf('notes')

      const rows: any[] = []
      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(',').map(c => c.trim())
        const d = cols[domainIdx]
        if (!d) continue
        rows.push({
          domain: d,
          display_name: displayIdx >= 0 ? cols[displayIdx] || undefined : undefined,
          desired_category: catIdx >= 0 ? cols[catIdx] || undefined : undefined,
          email_for_submit: emailIdx >= 0 ? cols[emailIdx] || undefined : undefined,
          notes: notesIdx >= 0 ? cols[notesIdx] || undefined : undefined,
        })
      }
      setCsvParsed(rows)
    }
    reader.readAsText(file)
  }

  const importCsv = async () => {
    setCsvImporting(true)
    setCsvProgress({ done: 0, total: csvParsed.length, errors: 0 })
    let errors = 0
    for (let i = 0; i < csvParsed.length; i++) {
      try {
        await domainsApi.create(csvParsed[i])
      } catch { errors++ }
      setCsvProgress({ done: i + 1, total: csvParsed.length, errors })
    }
    setCsvImporting(false)
    queryClient.invalidateQueries({ queryKey: ['domains'] })
    toast.success(`Imported ${csvParsed.length - errors} domains${errors > 0 ? ` (${errors} failed)` : ''}`)
    if (errors === 0) onClose()
  }

  const tabClass = (t: string) =>
    `px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
      tab === t ? 'bg-card text-foreground border border-border border-b-transparent -mb-px' : 'text-muted-foreground hover:text-foreground'
    }`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-xl bg-card rounded-xl border border-border shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <h3 className="text-lg font-semibold">Add Domains</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>

        <div className="flex px-6 gap-1 border-b border-border">
          <button onClick={() => setTab('manual')} className={tabClass('manual')}>Manual Entry</button>
          <button onClick={() => setTab('csv')} className={tabClass('csv')}>CSV Import</button>
        </div>

        <div className="px-6 py-5">
          {error && <div className="p-3 mb-4 rounded-md bg-destructive/15 text-destructive text-sm">{error}</div>}

          {tab === 'manual' ? (
            <>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Domain *</label>
                  <input type="text" value={domain} onChange={e => setDomain(e.target.value)} placeholder="example.com"
                    className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring" autoFocus />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">Display Name</label>
                    <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="My Website"
                      className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">Desired Category</label>
                    <select value={category} onChange={e => setCategory(e.target.value)}
                      className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring">
                      <option value="">Select...</option>
                      {categories.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Email for Submissions</label>
                  <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@example.com"
                    className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Notes</label>
                  <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} placeholder="Optional notes..."
                    className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring resize-none" />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-5">
                <button onClick={onClose} className="px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent">Cancel</button>
                <button
                  onClick={() => mutation.mutate({ domain, display_name: displayName || undefined, desired_category: category || undefined, email_for_submit: email || undefined, notes: notes || undefined })}
                  disabled={!domain || mutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:brightness-110 disabled:opacity-50 transition-all"
                >
                  {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
                  {mutation.isPending ? 'Adding...' : 'Add Domain'}
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-md bg-accent/50 border border-border">
                  <div>
                    <p className="text-sm font-medium">CSV Template</p>
                    <p className="text-xs text-muted-foreground mt-0.5">Download the template, fill it in, then upload</p>
                  </div>
                  <button onClick={downloadTemplate}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium border border-border hover:bg-accent transition-colors">
                    <Download size={13} /> Download Template
                  </button>
                </div>

                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Upload CSV File</label>
                  <div
                    className="border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary/40 transition-colors cursor-pointer"
                    onClick={() => document.getElementById('csv-file-input')?.click()}
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('border-primary/40') }}
                    onDragLeave={e => e.currentTarget.classList.remove('border-primary/40')}
                    onDrop={e => { e.preventDefault(); e.currentTarget.classList.remove('border-primary/40'); if (e.dataTransfer.files[0]) handleCsvFile(e.dataTransfer.files[0]) }}
                  >
                    <input id="csv-file-input" type="file" accept=".csv" className="hidden"
                      onChange={e => { if (e.target.files?.[0]) handleCsvFile(e.target.files[0]) }} />
                    {csvFile ? (
                      <div>
                        <p className="text-sm font-medium">{csvFile.name}</p>
                        <p className="text-xs text-muted-foreground mt-1">{csvParsed.length} domain{csvParsed.length !== 1 ? 's' : ''} found</p>
                      </div>
                    ) : (
                      <div>
                        <Download size={20} className="mx-auto text-muted-foreground/40 mb-2" />
                        <p className="text-sm text-muted-foreground">Click or drag & drop a CSV file</p>
                        <p className="text-xs text-muted-foreground/60 mt-1">Required column: domain. Optional: display_name, desired_category, email_for_submit, notes</p>
                      </div>
                    )}
                  </div>
                </div>

                {csvParsed.length > 0 && (
                  <div className="rounded-md border border-border overflow-hidden max-h-40 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border bg-[hsl(var(--table-header,var(--secondary)))] text-muted-foreground">
                          <th className="px-3 py-1.5 text-left font-medium">Domain</th>
                          <th className="px-3 py-1.5 text-left font-medium">Category</th>
                          <th className="px-3 py-1.5 text-left font-medium">Email</th>
                        </tr>
                      </thead>
                      <tbody>
                        {csvParsed.slice(0, 20).map((row, i) => (
                          <tr key={i} className="border-b border-border">
                            <td className="px-3 py-1.5 font-medium">{row.domain}</td>
                            <td className="px-3 py-1.5 text-muted-foreground">{row.desired_category || '--'}</td>
                            <td className="px-3 py-1.5 text-muted-foreground">{row.email_for_submit || '--'}</td>
                          </tr>
                        ))}
                        {csvParsed.length > 20 && (
                          <tr><td colSpan={3} className="px-3 py-1.5 text-muted-foreground text-center">...and {csvParsed.length - 20} more</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}

                {csvImporting && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Importing...</span>
                      <span>{csvProgress.done}/{csvProgress.total}{csvProgress.errors > 0 ? ` (${csvProgress.errors} errors)` : ''}</span>
                    </div>
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${(csvProgress.done / csvProgress.total) * 100}%` }} />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 mt-5">
                <button onClick={onClose} className="px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent">Cancel</button>
                <button
                  onClick={importCsv}
                  disabled={csvParsed.length === 0 || csvImporting}
                  className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:brightness-110 disabled:opacity-50 transition-all"
                >
                  {csvImporting && <Loader2 size={14} className="animate-spin" />}
                  {csvImporting ? `Importing ${csvProgress.done}/${csvProgress.total}...` : `Import ${csvParsed.length} Domain${csvParsed.length !== 1 ? 's' : ''}`}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
