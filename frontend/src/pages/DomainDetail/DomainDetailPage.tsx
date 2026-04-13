import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { domainsApi, jobsApi, vendorsApi } from '@/api/client'
import toast from 'react-hot-toast'
import { CATEGORIES, HIDDEN_VENDORS } from '@/lib/constants'
import { useWebSocket } from '@/context/WebSocketContext'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { ArrowLeft, Play, Send, RefreshCw, Save, Loader2 } from 'lucide-react'

export default function DomainDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { messages } = useWebSocket()

  const { data: domain } = useQuery({
    queryKey: ['domain', id],
    queryFn: () => domainsApi.get(id!).then(r => r.data),
  })

  const { data: results, refetch: refetchResults } = useQuery({
    queryKey: ['domain-results', id],
    queryFn: () => domainsApi.results(id!).then(r => r.data),
    refetchInterval: 2000,
  })

  // Optimistic "just clicked" tracker: vendor name → true for ~1.5s after a
  // re-check/submit click, so the card shows the running badge even if the
  // next refetch hasn't yet caught the worker's 'running' row write.
  const [pendingVendors, setPendingVendors] = useState<Set<string>>(new Set())
  const markPending = (vendor: string) => {
    setPendingVendors(prev => { const next = new Set(prev); next.add(vendor); return next })
    setTimeout(() => {
      setPendingVendors(prev => { const next = new Set(prev); next.delete(vendor); return next })
    }, 15000)
  }

  const { data: vendors } = useQuery({
    queryKey: ['vendors'],
    queryFn: () => vendorsApi.list().then(r => r.data),
  })

  const { data: history } = useQuery({
    queryKey: ['domain-history', id],
    queryFn: () => domainsApi.history(id!, { per_page: 20 }).then(r => r.data),
  })

  const checkMutation = useMutation({
    mutationFn: (vendor?: string) => jobsApi.check({ domain_id: id!, vendor }),
    onMutate: (vendor) => { if (vendor) markPending(vendor) },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      refetchResults()
    },
  })

  const reputationMutation = useMutation({
    mutationFn: (vendor?: string) => jobsApi.reputation({ domain_id: id!, vendor }),
    onMutate: (vendor) => { if (vendor) markPending(vendor) },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      refetchResults()
    },
    onError: (_, vendor) => toast.error(`Reputation check failed${vendor ? ` for ${vendor}` : ''}`),
  })

  const submitMutation = useMutation({
    mutationFn: (vendor?: string) => jobsApi.submit({ domain_id: id!, vendor }),
    onMutate: (vendor) => { if (vendor) markPending(vendor) },
    onSuccess: () => refetchResults(),
  })

  // Editing state
  const [editing, setEditing] = useState(false)
  const [desiredCategory, setDesiredCategory] = useState('')
  const [notes, setNotes] = useState('')
  const [customText, setCustomText] = useState('')
  const [emailForSubmit, setEmailForSubmit] = useState('')

  const startEdit = () => {
    setDesiredCategory(domain?.desired_category || '')
    setNotes(domain?.notes || '')
    setCustomText(domain?.custom_text || '')
    setEmailForSubmit(domain?.email_for_submit || '')
    setEditing(true)
  }

  const saveMutation = useMutation({
    mutationFn: () => domainsApi.update(id!, {
      desired_category: desiredCategory || null,
      notes: notes || null,
      custom_text: customText || null,
      email_for_submit: emailForSubmit || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['domain', id] })
      setEditing(false)
    },
  })

  const categories = CATEGORIES

  // Build result lookup by vendor name
  const resultMap: Record<string, any> = {}
  results?.forEach((r: any) => {
    const vendorName = vendors?.find((v: any) => v.id === r.vendor_id)?.name
    if (vendorName) resultMap[vendorName] = r
  })

  const categoryVendors = vendors?.filter((v: any) => v.vendor_type === 'category' && !HIDDEN_VENDORS.has(v.name)) || []
  const reputationVendors = vendors?.filter((v: any) => v.vendor_type === 'reputation') || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/domains')} className="p-2 rounded-md hover:bg-accent"><ArrowLeft size={18} /></button>
        <div className="flex-1">
          <h2 className="text-2xl font-bold tracking-tight">{domain?.domain}</h2>
          <p className="text-muted-foreground text-sm">{domain?.display_name || 'Domain Detail'}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => checkMutation.mutate()} className="flex items-center gap-2 px-3 py-2 rounded-md border border-border text-sm hover:bg-accent">
            <Play size={14} /> Check All
          </button>
          <button onClick={() => reputationMutation.mutate()} className="flex items-center gap-2 px-3 py-2 rounded-md border border-border text-sm hover:bg-accent">
            <RefreshCw size={14} /> Reputation
          </button>
          {domain?.desired_category && (
            <button onClick={() => submitMutation.mutate()} className="flex items-center gap-2 px-3 py-2 rounded-md bg-primary text-primary-foreground text-sm hover:opacity-90">
              <Send size={14} /> Submit All
            </button>
          )}
        </div>
      </div>

      {/* Domain Config */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Configuration</h3>
          {!editing ? (
            <button onClick={startEdit} className="text-sm text-primary hover:underline">Edit</button>
          ) : (
            <button onClick={() => saveMutation.mutate()} className="flex items-center gap-1 text-sm text-primary hover:underline">
              <Save size={14} /> Save
            </button>
          )}
        </div>

        {editing ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Desired Category</label>
              <select value={desiredCategory} onChange={e => setDesiredCategory(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm">
                <option value="">None</option>
                {categories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Email for Submit</label>
              <input type="email" value={emailForSubmit} onChange={e => setEmailForSubmit(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium mb-1">Notes</label>
              <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm resize-none" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium mb-1">Custom Text (for submissions)</label>
              <textarea value={customText} onChange={e => setCustomText(e.target.value)} rows={2}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm resize-none" />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><p className="text-muted-foreground">Category</p><p className="font-medium mt-1">{domain?.desired_category || 'Not set'}</p></div>
            <div><p className="text-muted-foreground">Email</p><p className="font-medium mt-1">{domain?.email_for_submit || 'Not set'}</p></div>
            <div><p className="text-muted-foreground">Notes</p><p className="font-medium mt-1">{domain?.notes || 'None'}</p></div>
            <div><p className="text-muted-foreground">Custom Text</p><p className="font-medium mt-1">{domain?.custom_text || 'None'}</p></div>
          </div>
        )}
      </div>

      {/* Category Vendor Cards */}
      <div>
        <h3 className="font-semibold mb-3">Category Vendors</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {categoryVendors.map((vendor: any) => {
            const r = resultMap[vendor.name]
            const busy = r?.status === 'running' || r?.status === 'pending' || pendingVendors.has(vendor.name)
            // For category vendors, only show a status badge for non-success states
            // (running, failed, cancelled, etc.). A successful check is conveyed by
            // the CategoryBadge below — an extra "Success" / "Clean" badge here would
            // be redundant and semantically wrong ("Clean" belongs to reputation).
            const showStatusBadge = busy || (r?.status && r.status !== 'success')
            return (
              <div key={vendor.id} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-sm">{vendor.display_name}</h4>
                  {showStatusBadge && <StatusBadge status={r?.status} loading={busy} />}
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Category</span>
                    <CategoryBadge category={r?.category} desired={domain?.desired_category} />
                  </div>
                  {r?.completed_at && !busy && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Last Check</span>
                      <span className="text-xs">{new Date(r.completed_at).toLocaleString()}</span>
                    </div>
                  )}
                </div>
                <div className="flex gap-1 mt-3">
                  <button
                    onClick={() => checkMutation.mutate(vendor.name)}
                    disabled={busy}
                    className={`flex-1 py-1.5 rounded text-xs font-medium text-center transition-colors ${
                      busy ? 'bg-muted/40 text-muted-foreground/30 cursor-not-allowed' : 'border border-border hover:bg-accent'
                    }`}
                  >
                    {busy ? <Loader2 size={10} className="animate-spin inline" /> : 'Re-check'}
                  </button>
                  {vendor.supports_submit && domain?.desired_category && (
                    <button
                      onClick={() => submitMutation.mutate(vendor.name)}
                      disabled={busy}
                      className={`flex-1 py-1.5 rounded text-xs font-medium text-center transition-colors ${
                        busy ? 'bg-primary/10 text-primary/30 cursor-not-allowed' : 'bg-primary text-primary-foreground hover:opacity-90'
                      }`}
                    >
                      Submit
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Reputation Vendors */}
      <div>
        <h3 className="font-semibold mb-3">Reputation Vendors</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {reputationVendors.map((vendor: any) => {
            const r = resultMap[vendor.name]
            const busy = r?.status === 'running' || r?.status === 'pending' || pendingVendors.has(vendor.name)
            // Reputation aggregates may live in `reputation` (new bridge) or `category` (old rows)
            const repString: string = r?.reputation || r?.category || ''
            const repLower = repString.toLowerCase()
            let badgeStatus: string | undefined = r?.status
            if (r?.status === 'success') {
              if (repLower.startsWith('malicious')) badgeStatus = 'malicious'
              else if (repLower.startsWith('suspicious')) badgeStatus = 'suspicious'
              else if (repLower.startsWith('error')) badgeStatus = 'error'
              else badgeStatus = 'clean'
            }
            return (
              <div key={vendor.id} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-sm">{vendor.display_name}</h4>
                  <StatusBadge status={busy ? undefined : badgeStatus} loading={busy} />
                </div>
                {repString && <p className="text-xs text-muted-foreground">{repString}</p>}
                {r?.completed_at && !busy && (
                  <p className="text-[10px] text-muted-foreground/60 mt-1">
                    Last check: {new Date(r.completed_at).toLocaleString()}
                  </p>
                )}
                {r?.error_message && <p className="text-xs text-red-500 mt-1 truncate">{r.error_message.split('\n')[0]}</p>}
                <button
                  onClick={() => reputationMutation.mutate(vendor.name)}
                  disabled={busy}
                  className={`w-full mt-3 py-1.5 rounded text-xs font-medium text-center transition-colors ${
                    busy
                      ? 'bg-muted/40 text-muted-foreground/30 cursor-not-allowed'
                      : 'border border-border hover:bg-accent'
                  }`}
                >
                  {busy ? <Loader2 size={10} className="animate-spin inline" /> : 'Re-check'}
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* History */}
      {history?.items && history.items.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="p-4 border-b border-border">
            <h3 className="font-semibold">Check History</h3>
          </div>
          <div className="divide-y divide-border max-h-64 overflow-y-auto">
            {history.items.map((h: any) => (
              <div key={h.id} className="px-4 py-3 flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <StatusBadge status={h.status} />
                  <span>{vendors?.find((v: any) => v.id === h.vendor_id)?.display_name || 'Unknown'}</span>
                  {h.category && <CategoryBadge category={h.category} desired={domain?.desired_category} />}
                </div>
                <span className="text-xs text-muted-foreground">{new Date(h.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
