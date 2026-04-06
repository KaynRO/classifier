import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { domainsApi, jobsApi, vendorsApi } from '@/api/client'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { Plus, Search, Trash2, ChevronDown, ChevronRight, Save, X, Loader2, ScanSearch, Download, PlayCircle, SendHorizonal } from 'lucide-react'
import toast from 'react-hot-toast'
import { CATEGORIES, HIDDEN_VENDORS } from '@/lib/constants'

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
          <table className="text-sm" style={{ minWidth: `${220 + 150 + categoryVendors.length * 195 + 50}px` }}>
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
      <th className="px-5 py-2.5 text-left font-medium w-[220px] sticky left-0 bg-card z-10">Domain</th>
      <th className="px-4 py-2.5 text-left font-medium w-[150px]">Desired Category</th>
      {categoryVendors.map((v: any) => (
        <th key={v.id} className="px-4 py-2.5 text-center font-medium w-[195px]">
          <div className="flex flex-col items-center gap-0.5">
            <span>{v.display_name}</span>
            {latestPerVendor[v.id] && (
              <span className="text-[9px] font-normal normal-case text-muted-foreground/50">
                {timeAgo(latestPerVendor[v.id]!)}
              </span>
            )}
          </div>
        </th>
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
  const [busyVendors, setBusyVendors] = useState<Set<string>>(new Set())

  const { data: results } = useQuery({
    queryKey: ['domain-results', domain.id],
    queryFn: () => domainsApi.results(domain.id).then(r => r.data),
    refetchInterval: 4000,
  })

  const checkMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.reputation({ domain_id: domain.id }),
    onMutate: (vendor) => { setBusyVendors(prev => new Set(prev).add(vendor)); toast('Verifying...', { icon: '🔍' }) },
    onError: () => toast.error('Verification failed'),
    onSettled: (_, __, vendor) => {
      setTimeout(() => {
        setBusyVendors(prev => { const s = new Set(prev); s.delete(vendor); return s })
        queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] })
      }, 3000)
    },
  })

  const resultMap: Record<number, any> = {}
  results?.forEach((r: any) => { resultMap[r.vendor_id] = r })

  return (
    <tr className="border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors">
      <td className="px-5 py-2.5">
        <span className="font-medium text-primary/90 dark:text-[hsl(265,50%,72%)]">{domain.domain}</span>
      </td>
      {reputationVendors.map((v: any) => {
        const r = resultMap[v.id]
        const isBusy = busyVendors.has(v.name) || r?.status === 'running' || r?.status === 'pending'
        return (
          <td key={v.id} className="px-4 py-2.5">
            <div className="flex items-start gap-3">
              <div className="flex flex-col min-w-[70px]">
                <StatusBadge status={r?.status === 'success' ? 'clean' : r?.status} loading={isBusy} />
                {r?.completed_at && !isBusy && (
                  <span className="text-[9px] text-muted-foreground/60 mt-1">{timeAgo(r.completed_at)}</span>
                )}
              </div>
              <button
                onClick={() => checkMutation.mutate(v.name)}
                disabled={isBusy}
                className={`mt-px px-2.5 py-1 rounded text-[11px] font-medium border transition-all duration-200 min-h-[28px] ${
                  isBusy
                    ? 'border-border/50 text-muted-foreground/30 cursor-not-allowed bg-muted/30'
                    : 'border-border hover:bg-accent hover:text-accent-foreground'
                }`}
              >
                {isBusy ? <Loader2 size={10} className="animate-spin" /> : 'Verify'}
              </button>
            </div>
          </td>
        )
      })}
      <td className="px-3 py-2.5 text-center">
        <button onClick={onDelete}
          className="p-1 rounded hover:bg-destructive/15 text-muted-foreground/50 hover:text-destructive transition-colors" title="Delete">
          <Trash2 size={13} />
        </button>
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

  const startBusy = (key: string) => setBusyVendors(prev => new Set(prev).add(key))
  const clearBusy = (key: string) => {
    setTimeout(() => {
      setBusyVendors(prev => { const s = new Set(prev); s.delete(key); return s })
      queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] })
    }, 3000)
  }

  const checkVendorMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.check({
      domain_id: domain.id,
      vendor: vendor === '__all__' ? undefined : vendor,
    }),
    onMutate: (vendor) => {
      if (vendor !== '__all__') { startBusy(`check-${vendor}`); toast(`Checking ${vendor}...`, { icon: '🔄' }) }
    },
    onError: (_, vendor) => toast.error(`Check failed${vendor !== '__all__' ? ` for ${vendor}` : ''}`),
    onSettled: (_, __, vendor) => {
      if (vendor !== '__all__') clearBusy(`check-${vendor}`)
      queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] })
    },
  })

  const submitVendorMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.submit({
      domain_id: domain.id,
      vendor: vendor === '__all__' ? undefined : vendor,
    }),
    onMutate: (vendor) => {
      if (vendor !== '__all__') { startBusy(`submit-${vendor}`); toast(`Submitting to ${vendor}...`, { icon: '📤' }) }
    },
    onError: (_, vendor) => toast.error(`Submit failed${vendor !== '__all__' ? ` for ${vendor}` : ''}`),
    onSettled: (_, __, vendor) => {
      if (vendor !== '__all__') clearBusy(`submit-${vendor}`)
      queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] })
    },
  })

  const resultMap: Record<number, any> = {}
  results?.forEach((r: any) => { resultMap[r.vendor_id] = r })

  return (
    <>
      <tr className="border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors">
        <td className="px-5 py-2.5 sticky left-0 bg-card z-10">
          <div className="flex items-center gap-2">
            <button onClick={onToggle} className="text-muted-foreground hover:text-foreground transition-colors">
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            <span className="font-medium text-primary/90 dark:text-[hsl(265,50%,72%)]">{domain.domain}</span>
          </div>
        </td>
        <td className="px-4 py-2.5">
          {domain.desired_category
            ? <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-primary/15 text-primary dark:text-[hsl(265,50%,72%)]">{domain.desired_category}</span>
            : <span className="text-[11px] text-muted-foreground/50 italic">Not Set</span>
          }
        </td>
        {categoryVendors.map((v: any) => {
          const r = resultMap[v.id]
          const isCheckBusy = busyVendors.has(`check-${v.name}`) || r?.status === 'running' || r?.status === 'pending'
          const isSubmitBusy = busyVendors.has(`submit-${v.name}`)
          const anyBusy = isCheckBusy || isSubmitBusy
          return (
            <td key={v.id} className="px-3 py-2 text-center">
              <div className="flex flex-col items-center gap-1">
                {/* Result */}
                {isCheckBusy ? (
                  <StatusBadge status="running" />
                ) : r?.status === 'success' ? (
                  <CategoryBadge category={r.category} desired={domain.desired_category} />
                ) : (
                  <StatusBadge status={r?.status} />
                )}
                {/* Buttons */}
                <div className="flex items-center gap-1 mt-0.5">
                  <button
                    onClick={() => checkVendorMutation.mutate(v.name)}
                    disabled={isCheckBusy}
                    className={`px-2.5 py-1 rounded text-[11px] min-h-[28px] font-medium border transition-all duration-200 ${
                      isCheckBusy
                        ? 'border-border/40 text-muted-foreground/30 cursor-not-allowed bg-muted/20'
                        : 'border-border hover:bg-accent hover:text-accent-foreground'
                    }`}
                  >
                    {isCheckBusy ? <Loader2 size={9} className="animate-spin" /> : 'Check'}
                  </button>
                  {v.supports_submit && (
                    <button
                      onClick={() => submitVendorMutation.mutate(v.name)}
                      disabled={isSubmitBusy || isCheckBusy || !domain.desired_category}
                      title={!domain.desired_category ? 'Set desired category first' : `Submit ${domain.desired_category} to ${v.display_name}`}
                      className={`px-2.5 py-1 rounded text-[11px] min-h-[28px] font-medium border transition-all duration-200 ${
                        isSubmitBusy || isCheckBusy
                          ? 'border-primary/20 text-primary/30 cursor-not-allowed bg-primary/5'
                          : !domain.desired_category
                            ? 'border-border/30 text-muted-foreground/30 cursor-not-allowed'
                            : 'border-primary/30 text-primary hover:bg-primary/10'
                      }`}
                    >
                      {isSubmitBusy ? <Loader2 size={9} className="animate-spin" /> : 'Submit'}
                    </button>
                  )}
                </div>
              </div>
            </td>
          )
        })}
        <td className="px-3 py-2 text-center">
          <div className="flex flex-col items-center gap-1">
            <button
              onClick={() => { checkVendorMutation.mutate('__all__'); toast('Checking all vendors...', { icon: '🔄' }) }}
              className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors" title="Check All Vendors">
              <PlayCircle size={15} />
            </button>
            {domain.desired_category && (
              <button
                onClick={() => { submitVendorMutation.mutate('__all__'); toast('Submitting to all vendors...', { icon: '📤' }) }}
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
          <td colSpan={categoryVendors.length + 3} className="px-0 py-0">
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
  const [domain, setDomain] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [category, setCategory] = useState('')
  const [email, setEmail] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg bg-card rounded-xl border border-border p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold">Add Domain</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>

        {error && <div className="p-3 mb-4 rounded-md bg-destructive/15 text-destructive text-sm">{error}</div>}

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
      </div>
    </div>
  )
}
