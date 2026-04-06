import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { domainsApi, jobsApi, vendorsApi } from '@/api/client'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { Plus, Search, Trash2, ChevronDown, ChevronRight, Save, X, Loader2, ScanSearch } from 'lucide-react'

// Vendors to hide from the dashboard
const HIDDEN_VENDORS = new Set(['lightspeedsystems'])

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['domains'] }),
  })

  const bulkCheckMutation = useMutation({
    mutationFn: () => jobsApi.bulkCheck(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setScanningAll(false)
    },
    onMutate: () => setScanningAll(true),
  })

  const categoryVendors = vendors?.filter((v: any) => v.vendor_type === 'category' && !HIDDEN_VENDORS.has(v.name)) || []
  const reputationVendors = vendors?.filter((v: any) => v.vendor_type === 'reputation' && !HIDDEN_VENDORS.has(v.name)) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Domain Categorization & Safety</h2>
          <p className="text-sm text-muted-foreground mt-0.5">Threat reputation and web proxy categorization across security vendors</p>
        </div>
        <div className="flex gap-2">
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
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-5 py-2.5 text-left font-medium">Domain</th>
              {reputationVendors.map((v: any) => (
                <th key={v.id} className="px-4 py-2.5 text-left font-medium">{v.display_name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.items?.map((domain: any) => (
              <SafetyRow key={domain.id} domain={domain} reputationVendors={reputationVendors} />
            ))}
            {isLoading && <LoadingRow cols={1 + reputationVendors.length} />}
            {!isLoading && (!data?.items || data.items.length === 0) && (
              <EmptyRow cols={1 + reputationVendors.length} text="No domains yet" />
            )}
          </tbody>
        </table>
      </section>

      {/* WEB PROXY CATEGORIZATION */}
      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border bg-[hsl(var(--table-header,var(--secondary)))]">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Web Proxy Categorization</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="text-sm" style={{ minWidth: `${200 + 140 + categoryVendors.length * 170 + 40}px` }}>
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-5 py-2.5 text-left font-medium w-[200px] sticky left-0 bg-card z-10">Domain</th>
                <th className="px-4 py-2.5 text-left font-medium w-[140px]">Desired Category</th>
                {categoryVendors.map((v: any) => (
                  <th key={v.id} className="px-3 py-2.5 text-center font-medium w-[170px]">{v.display_name}</th>
                ))}
                <th className="px-3 py-2.5 text-center font-medium w-[40px]"></th>
              </tr>
            </thead>
            <tbody>
              {data?.items?.map((domain: any) => (
                <CategorizationRow
                  key={domain.id}
                  domain={domain}
                  categoryVendors={categoryVendors}
                  expanded={expandedId === domain.id}
                  onToggle={() => setExpandedId(prev => prev === domain.id ? null : domain.id)}
                  onDelete={() => deleteMutation.mutate(domain.id)}
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
    </div>
  )
}

function LoadingRow({ cols }: { cols: number }) {
  return <tr><td colSpan={cols} className="px-5 py-8 text-center text-muted-foreground text-sm"><Loader2 size={16} className="animate-spin inline mr-2" />Loading...</td></tr>
}
function EmptyRow({ cols, text }: { cols: number; text: string }) {
  return <tr><td colSpan={cols} className="px-5 py-8 text-center text-muted-foreground text-sm">{text}</td></tr>
}


/* ========== SAFETY ROW ========== */
function SafetyRow({ domain, reputationVendors }: { domain: any; reputationVendors: any[] }) {
  const queryClient = useQueryClient()
  const [busyVendors, setBusyVendors] = useState<Set<string>>(new Set())

  const { data: results } = useQuery({
    queryKey: ['domain-results', domain.id],
    queryFn: () => domainsApi.results(domain.id).then(r => r.data),
    refetchInterval: 4000,
  })

  const checkMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.reputation({ domain_id: domain.id }),
    onMutate: (vendor) => setBusyVendors(prev => new Set(prev).add(vendor)),
    onSettled: (_, __, vendor) => {
      // Don't clear immediately — let the refetch show the running state, clear after delay
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
            <div className="flex items-center gap-2">
              <div className="flex flex-col">
                <StatusBadge status={r?.status === 'success' ? 'clean' : r?.status} loading={isBusy} />
                {r?.completed_at && !isBusy && (
                  <span className="text-[9px] text-muted-foreground/60 mt-0.5">{timeAgo(r.completed_at)}</span>
                )}
              </div>
              <button
                onClick={() => checkMutation.mutate(v.name)}
                disabled={isBusy}
                className={`px-2 py-1 rounded text-[11px] font-medium border transition-all duration-200 ${
                  isBusy
                    ? 'border-border/50 text-muted-foreground/30 cursor-not-allowed bg-muted/30'
                    : 'border-border hover:bg-accent hover:text-accent-foreground'
                }`}
              >
                {isBusy ? <Loader2 size={10} className="animate-spin" /> : 'verify'}
              </button>
            </div>
          </td>
        )
      })}
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
    mutationFn: (vendor: string) => jobsApi.check({ domain_id: domain.id, vendor }),
    onMutate: (vendor) => startBusy(`check-${vendor}`),
    onSettled: (_, __, vendor) => clearBusy(`check-${vendor}`),
  })

  const submitVendorMutation = useMutation({
    mutationFn: (vendor: string) => jobsApi.submit({ domain_id: domain.id, vendor }),
    onMutate: (vendor) => startBusy(`submit-${vendor}`),
    onSettled: (_, __, vendor) => clearBusy(`submit-${vendor}`),
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
            : <span className="text-[11px] text-muted-foreground/50 italic">not set</span>
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
                {/* Last checked timestamp */}
                {r?.completed_at && !isCheckBusy && (
                  <span className="text-[9px] text-muted-foreground/60">{timeAgo(r.completed_at)}</span>
                )}
                {/* Buttons */}
                <div className="flex items-center gap-1 mt-0.5">
                  <button
                    onClick={() => checkVendorMutation.mutate(v.name)}
                    disabled={isCheckBusy}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium border transition-all duration-200 ${
                      isCheckBusy
                        ? 'border-border/40 text-muted-foreground/30 cursor-not-allowed bg-muted/20'
                        : 'border-border hover:bg-accent hover:text-accent-foreground'
                    }`}
                  >
                    {isCheckBusy ? <Loader2 size={9} className="animate-spin" /> : 'check'}
                  </button>
                  {v.supports_submit && domain.desired_category && (
                    <button
                      onClick={() => submitVendorMutation.mutate(v.name)}
                      disabled={isSubmitBusy || isCheckBusy}
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium border transition-all duration-200 ${
                        isSubmitBusy || isCheckBusy
                          ? 'border-primary/20 text-primary/30 cursor-not-allowed bg-primary/5'
                          : 'border-primary/30 text-primary hover:bg-primary/10'
                      }`}
                    >
                      {isSubmitBusy ? <Loader2 size={9} className="animate-spin" /> : 'submit'}
                    </button>
                  )}
                </div>
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

  const categories = ['Business', 'Education', 'Finance', 'Health', 'News', 'Internet']

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
      onClose()
    },
    onError: (err: any) => setError(err.response?.data?.detail || 'Failed to add domain'),
  })

  const categories = ['Business', 'Education', 'Finance', 'Health', 'News', 'Internet']

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
