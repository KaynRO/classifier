import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { domainsApi, jobsApi, vendorsApi } from '@/api/client'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { Plus, Search, Trash2, ChevronDown, ChevronRight, Save, X, Loader2, ScanSearch, Download, PlayCircle, SendHorizonal } from 'lucide-react'
import toast from 'react-hot-toast'
import { CATEGORIES, HIDDEN_VENDORS, getManualUrl } from '@/lib/constants'
import { ExternalLink } from 'lucide-react'

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

export default function DomainsPage() {
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [scanningAll, setScanningAll] = useState(false)
  const [domainToDelete, setDomainToDelete] = useState<any>(null)
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

  const bulkCheckMutation = useMutation({
    mutationFn: () => jobsApi.bulkCheck(),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast.success('Scan started for all domains') },
    onError: () => toast.error('Failed to start bulk scan'),
    onMutate: () => setScanningAll(true),
    onSettled: () => setScanningAll(false),
  })

  const categoryVendors = vendors?.filter((v: any) => v.vendor_type === 'category' && !HIDDEN_VENDORS.has(v.name)) || []
  const reputationVendors = vendors?.filter((v: any) => v.vendor_type === 'reputation' && !HIDDEN_VENDORS.has(v.name)) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Domain Categorization & Safety</h2>
          <p className="text-sm text-muted-foreground mt-0.5">Threat reputation and web proxy categorization across security vendors</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              try {
                const res = await domainsApi.exportCsv()
                const url = window.URL.createObjectURL(new Blob([res.data]))
                const a = document.createElement('a')
                a.href = url
                a.download = `classifier_export_${new Date().toISOString().slice(0,10)}.csv`
                a.click()
                window.URL.revokeObjectURL(url)
                toast.success('Export downloaded')
              } catch { toast.error('Export failed') }
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent transition-colors"
          >
            <Download size={14} /> Export CSV
          </button>
          <button
            onClick={() => bulkCheckMutation.mutate()}
            disabled={scanningAll}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent transition-colors disabled:opacity-50"
          >
            {scanningAll ? <Loader2 size={14} className="animate-spin" /> : <ScanSearch size={14} />}
            Scan All Domains
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:brightness-110 transition-all"
          >
            <Plus size={14} /> Add Domain
          </button>
        </div>
      </div>

      {/* Search */}
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

      {/* SAFETY STATUS */}
      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border bg-[hsl(var(--table-header,var(--secondary)))]">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Safety Status</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="text-sm" style={{ minWidth: `${220 + reputationVendors.length * 210 + 50}px` }}>
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-5 py-2.5 text-left font-medium w-[220px]">Domain</th>
                {reputationVendors.map((v: any) => (
                  <th key={v.id} className="px-4 py-2.5 text-left font-medium w-[210px]">{v.display_name}</th>
                ))}
                <th className="px-3 py-2.5 w-[50px]"></th>
              </tr>
            </thead>
            <tbody>
              {data?.items?.map((domain: any) => (
                <SafetyRow key={domain.id} domain={domain} reputationVendors={reputationVendors} onDelete={() => setDomainToDelete(domain)} />
              ))}
              {isLoading && <LoadingRow cols={2 + reputationVendors.length} />}
              {!isLoading && (!data?.items || data.items.length === 0) && (
                <EmptyRow cols={2 + reputationVendors.length} text="No domains yet" />
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* WEB PROXY CATEGORIZATION */}
      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border bg-[hsl(var(--table-header,var(--secondary)))]">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Web Proxy Categorization</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="text-sm" style={{ minWidth: `${240 + categoryVendors.length * 195 + 80}px` }}>
            <thead>
              <VendorHeaders categoryVendors={categoryVendors} domains={data?.items || []} />
            </thead>
            <tbody>
              {data?.items?.map((domain: any) => (
                <CategorizationRow
                  key={domain.id}
                  domain={domain}
                  categoryVendors={categoryVendors}
                  expanded={expandedId === domain.id}
                  onToggle={() => setExpandedId(prev => prev === domain.id ? null : domain.id)}
                  onDelete={() => setDomainToDelete(domain)}
                />
              ))}
              {isLoading && <LoadingRow cols={2 + categoryVendors.length + 1} />}
              {!isLoading && (!data?.items || data.items.length === 0) && (
                <EmptyRow cols={2 + categoryVendors.length + 1} text="No domains yet. Click &quot;Add Domain&quot; to get started." />
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

/* ========== VENDOR COLUMN HEADERS WITH TIMESTAMPS ========== */
function VendorHeaders({ categoryVendors, domains }: { categoryVendors: any[]; domains: any[] }) {
  // Aggregate latest check time per vendor across all domains
  const allResults = useQuery({
    queryKey: ['all-results-for-headers'],
    queryFn: async () => {
      if (!domains.length) return []
      const promises = domains.slice(0, 10).map(d => domainsApi.results(d.id).then(r => r.data))
      return (await Promise.all(promises)).flat()
    },
    enabled: domains.length > 0,
    staleTime: 10000,
  })

  const latestPerVendor: Record<number, string | null> = {}
  allResults.data?.forEach((r: any) => {
    if (r.completed_at) {
      const existing = latestPerVendor[r.vendor_id]
      if (!existing || r.completed_at > existing) {
        latestPerVendor[r.vendor_id] = r.completed_at
      }
    }
  })

  return (
    <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
      <th className="px-5 py-2.5 text-left font-medium w-[240px] sticky left-0 bg-card z-10">Domain</th>
      {categoryVendors.map((v: any) => (
        <th key={v.id} className="px-4 py-2.5 text-center font-medium w-[195px]">{v.display_name}</th>
      ))}
      <th className="px-3 py-2.5 text-center font-medium w-[80px]">Actions</th>
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


/* ========== SAFETY ROW ========== */
function SafetyRow({ domain, reputationVendors, onDelete }: { domain: any; reputationVendors: any[]; onDelete: () => void }) {
  const queryClient = useQueryClient()

  const { data: results } = useQuery({
    queryKey: ['domain-results', domain.id],
    queryFn: () => domainsApi.results(domain.id).then(r => r.data),
    refetchInterval: 4000,
  })

  // Only use 'reputation' action results for the Safety table
  const resultMap: Record<number, any> = {}
  results?.filter((r: any) => r.action_type === 'reputation').forEach((r: any) => { resultMap[r.vendor_id] = r })

  const checkMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.reputation({ domain_id: domain.id }),
    onMutate: () => toast('Verifying...', { icon: '🔍' }),
    onError: () => toast.error('Verification failed'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }),
  })

  const cancelMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.cancelVendor(domain.id, vendor),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }); toast.success('Cancelled') },
    onError: () => toast.error('Cancel failed'),
  })

  return (
    <tr className="border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors">
      <td className="px-5 py-3 align-middle">
        <span className="font-medium text-primary/90 dark:text-[hsl(265,50%,72%)]">{domain.domain}</span>
      </td>
      {reputationVendors.map((v: any) => {
        const r = resultMap[v.id]
        const busy = r?.status === 'running' || r?.status === 'pending'
        const lastFailed = r?.status === 'failed'
        const manualUrl = lastFailed ? getManualUrl(v.name, 'check', domain.domain) : null
        return (
          <td key={v.id} className="px-4 py-3 align-middle">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2.5 h-[26px]">
                <StatusBadge
                  status={r?.status === 'success' ? 'clean' : r?.status}
                  loading={busy}
                  onCancel={busy ? () => cancelMutation.mutate(v.name) : undefined}
                />
                <button
                  onClick={() => checkMutation.mutate(v.name)}
                  disabled={busy}
                  className={`px-3 h-[26px] rounded-md text-[11px] font-medium transition-all duration-200 ${
                    busy
                      ? 'bg-muted/40 text-muted-foreground/30 cursor-not-allowed'
                      : 'bg-secondary hover:bg-accent text-secondary-foreground hover:text-accent-foreground'
                  }`}
                >
                  {busy ? <Loader2 size={10} className="animate-spin" /> : 'Verify'}
                </button>
              </div>
              {manualUrl && (
                <a
                  href={manualUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Automated check failed — open vendor page to verify manually"
                  className="inline-flex items-center gap-1 px-2 h-[22px] rounded-md text-[10px] font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 border border-amber-500/30 transition-colors w-fit"
                >
                  <ExternalLink size={9} />
                  Manual Check
                </a>
              )}
            </div>
          </td>
        )
      })}
      <td className="px-3 py-3 align-middle">
        <div className="flex items-center h-[26px]">
          <button onClick={onDelete}
            className="px-3 h-[26px] rounded-md text-[11px] font-medium bg-secondary hover:bg-destructive/15 text-muted-foreground/50 hover:text-destructive transition-all flex items-center" title="Delete">
            <Trash2 size={13} />
          </button>
        </div>
      </td>
    </tr>
  )
}


/* ========== CATEGORIZATION ROW ========== */
function CategorizationRow({ domain, categoryVendors, expanded, onToggle, onDelete }: {
  domain: any; categoryVendors: any[]; expanded: boolean; onToggle: () => void; onDelete: () => void
}) {
  const queryClient = useQueryClient()
  const [busyVendors, setBusyVendors] = useState<Set<string>>(new Set())

  const { data: results } = useQuery({
    queryKey: ['domain-results', domain.id],
    queryFn: () => domainsApi.results(domain.id).then(r => r.data),
    refetchInterval: 4000,
  })

  // Busy state is now driven entirely by DB status (persists across refresh/navigation)
  // The backend sets check_result.status='running' when a task starts

  const checkVendorMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.check({
      domain_id: domain.id,
      vendor: vendor === '__all__' ? undefined : vendor,
    }),
    onMutate: (vendor) => {
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

  // Only use 'check' action results for the Categorization table
  const resultMap: Record<number, any> = {}
  results?.filter((r: any) => r.action_type === 'check').forEach((r: any) => { resultMap[r.vendor_id] = r })
  // Separate map for submit results so we can surface a "Manual Submit" button on failure
  const submitResultMap: Record<number, any> = {}
  results?.filter((r: any) => r.action_type === 'submit').forEach((r: any) => { submitResultMap[r.vendor_id] = r })

  return (
    <>
      <tr className="border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors">
        <td className="px-5 py-2.5 sticky left-0 bg-card z-10">
          <div className="flex items-center gap-2">
            <button onClick={onToggle} className="text-muted-foreground hover:text-foreground transition-colors">
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            <div>
              <span className="font-medium text-primary/90 dark:text-[hsl(265,50%,72%)]">{domain.domain}</span>
              <div className="mt-0.5">
                {domain.desired_category
                  ? <span className="px-1.5 py-px rounded text-[10px] font-medium bg-primary/10 text-primary/70 dark:text-[hsl(265,40%,65%)]">{domain.desired_category}</span>
                  : <span className="text-[10px] text-muted-foreground/40 italic">No category set</span>
                }
              </div>
            </div>
          </div>
        </td>
        {categoryVendors.map((v: any) => {
          const r = resultMap[v.id]
          const sr = submitResultMap[v.id]
          const isCheckBusy = r?.status === 'running' || r?.status === 'pending'
          const isSubmitBusy = sr?.status === 'running' || sr?.status === 'pending'
          const checkFailed = r?.status === 'failed'
          const submitFailed = sr?.status === 'failed'
          const manualCheckUrl = checkFailed ? getManualUrl(v.name, 'check', domain.domain) : null
          const manualSubmitUrl = submitFailed && v.supports_submit ? getManualUrl(v.name, 'submit', domain.domain) : null
          return (
            <td key={v.id} className="px-3 py-2 text-center">
              <div className="flex flex-col items-center gap-1">
                {/* Result — show running badge whenever check OR submit is in-flight */}
                {isCheckBusy || isSubmitBusy ? (
                  <StatusBadge status="running" onCancel={() => cancelMutation.mutate(v.name)} />
                ) : r?.status === 'success' ? (
                  <CategoryBadge category={r.category} desired={domain.desired_category} />
                ) : (
                  <StatusBadge status={r?.status} />
                )}
                {/* Timestamp */}
                {r?.completed_at && !isCheckBusy && !isSubmitBusy && (
                  <span className="text-[9px] text-muted-foreground/50">{timeAgo(r.completed_at)}</span>
                )}
                {/* Buttons */}
                <div className="flex items-center gap-1 mt-0.5">
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
                {/* Manual fallback buttons — appear only after automation failed */}
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
        <td className="px-3 py-2 text-center">
          <div className="flex flex-col items-center gap-1">
            <button
              onClick={() => checkVendorMutation.mutate('__all__')}
              className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors" title="Check All Vendors">
              <PlayCircle size={15} />
            </button>
            {domain.desired_category && (
              <button
                onClick={() => submitVendorMutation.mutate('__all__')}
                className="p-1.5 rounded hover:bg-primary/10 text-primary/60 hover:text-primary transition-colors" title="Submit All Vendors">
                <SendHorizonal size={15} />
              </button>
            )}
            <button onClick={onDelete}
              className="p-1.5 rounded hover:bg-destructive/15 text-muted-foreground/30 hover:text-destructive transition-colors" title="Delete">
              <Trash2 size={13} />
            </button>
          </div>
        </td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan={categoryVendors.length + 2} className="px-0 py-0">
            <DomainConfigPanel domain={domain} />
          </td>
        </tr>
      )}
    </>
  )
}


/* ========== DOMAIN CONFIG PANEL ========== */
function DomainConfigPanel({ domain }: { domain: any }) {
  const queryClient = useQueryClient()
  const [desiredCategory, setDesiredCategory] = useState(domain.desired_category || '')
  const [emailForSubmit, setEmailForSubmit] = useState(domain.email_for_submit || '')
  const [notes, setNotes] = useState(domain.notes || '')
  const [customText, setCustomText] = useState(domain.custom_text || '')
  const [dirty, setDirty] = useState(false)

  const categories = CATEGORIES

  const saveMutation = useMutation({
    mutationFn: () => domainsApi.update(domain.id, {
      desired_category: desiredCategory || null,
      email_for_submit: emailForSubmit || null,
      notes: notes || null,
      custom_text: customText || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['domains'] })
      setDirty(false)
      toast.success('Configuration saved')
    },
  })

  const handleChange = (setter: Function) => (e: any) => {
    setter(e.target.value)
    setDirty(true)
  }

  return (
    <div className="bg-[hsl(var(--table-header,var(--secondary)))] border-t border-border px-6 py-4">
      <div className="flex items-end gap-4">
        <div className="flex-1 min-w-[140px]">
          <label className="block text-[11px] font-medium text-muted-foreground mb-1">Desired Category</label>
          <select value={desiredCategory} onChange={handleChange(setDesiredCategory)}
            className="w-full px-2.5 py-1.5 rounded border border-input bg-card text-sm focus:outline-none focus:ring-1 focus:ring-ring">
            <option value="">None</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-[180px]">
          <label className="block text-[11px] font-medium text-muted-foreground mb-1">Email for Submissions</label>
          <input type="email" value={emailForSubmit} onChange={handleChange(setEmailForSubmit)}
            className="w-full px-2.5 py-1.5 rounded border border-input bg-card text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="admin@example.com" />
        </div>
        <div className="flex-1 min-w-[140px]">
          <label className="block text-[11px] font-medium text-muted-foreground mb-1">Notes</label>
          <input type="text" value={notes} onChange={handleChange(setNotes)}
            className="w-full px-2.5 py-1.5 rounded border border-input bg-card text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="Optional notes..." />
        </div>
        <div className="flex-1 min-w-[140px]">
          <label className="block text-[11px] font-medium text-muted-foreground mb-1">Custom Submit Text</label>
          <input type="text" value={customText} onChange={handleChange(setCustomText)}
            className="w-full px-2.5 py-1.5 rounded border border-input bg-card text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="Custom reason..." />
        </div>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={!dirty || saveMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded text-sm font-medium bg-primary text-primary-foreground hover:brightness-110 transition-all disabled:opacity-40 whitespace-nowrap"
        >
          {saveMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          Save
        </button>
      </div>
    </div>
  )
}


/* ========== DELETE CONFIRM DIALOG ========== */
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


/* ========== ADD DOMAIN MODAL ========== */
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
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <h3 className="text-lg font-semibold">Add Domains</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>

        {/* Tabs */}
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
                {/* Template download */}
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

                {/* File upload */}
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

                {/* Preview parsed rows */}
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

                {/* Import progress */}
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
