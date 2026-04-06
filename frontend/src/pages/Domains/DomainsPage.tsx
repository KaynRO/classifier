import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { domainsApi, jobsApi, vendorsApi } from '@/api/client'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { Plus, Search, Play, Trash2, ChevronDown, ChevronRight, Send, RefreshCw, Save, X, Pencil } from 'lucide-react'

export default function DomainsPage() {
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['domains', search],
    queryFn: () => domainsApi.list({ search, per_page: 50 }).then(r => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => domainsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['domains'] }),
  })

  const checkMutation = useMutation({
    mutationFn: (domain_id: string) => jobsApi.check({ domain_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['domain-results'] })
    },
  })

  const bulkCheckMutation = useMutation({
    mutationFn: () => jobsApi.bulkCheck(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const toggleExpand = (id: string) => {
    setExpandedId(prev => prev === id ? null : id)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Domains</h2>
          <p className="text-muted-foreground mt-1">Manage your domain assets</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => bulkCheckMutation.mutate()}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent transition-colors"
          >
            <Play size={16} /> Check All
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <Plus size={16} /> Add Domain
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search domains..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Domains List */}
      <div className="space-y-2">
        {data?.items?.map((domain: any) => (
          <div key={domain.id} className="rounded-lg border border-border bg-card overflow-hidden">
            {/* Domain Row */}
            <div
              className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-accent/50 transition-colors"
              onClick={() => toggleExpand(domain.id)}
            >
              <button className="p-0.5 text-muted-foreground">
                {expandedId === domain.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>
              <div className="flex-1 min-w-0">
                <span className="font-medium">{domain.domain}</span>
                {domain.display_name && (
                  <span className="ml-2 text-xs text-muted-foreground">{domain.display_name}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {domain.desired_category ? (
                  <span className="px-2 py-0.5 rounded bg-secondary text-xs font-medium">{domain.desired_category}</span>
                ) : (
                  <span className="text-xs text-muted-foreground">No category</span>
                )}
                <span className="text-xs text-muted-foreground">{new Date(domain.created_at).toLocaleDateString()}</span>
                <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  <button onClick={() => checkMutation.mutate(domain.id)}
                    className="p-1.5 rounded hover:bg-accent" title="Check all vendors">
                    <Play size={14} />
                  </button>
                  <button onClick={() => deleteMutation.mutate(domain.id)}
                    className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive" title="Delete">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>

            {/* Expanded Panel */}
            {expandedId === domain.id && (
              <ExpandedDomainPanel domain={domain} />
            )}
          </div>
        ))}

        {isLoading && (
          <div className="rounded-lg border border-border bg-card px-4 py-12 text-center text-muted-foreground">Loading...</div>
        )}
        {!isLoading && (!data?.items || data.items.length === 0) && (
          <div className="rounded-lg border border-border bg-card px-4 py-12 text-center text-muted-foreground">
            No domains found. Click "Add Domain" to get started.
          </div>
        )}
      </div>

      {showAdd && <AddDomainModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}


function ExpandedDomainPanel({ domain }: { domain: any }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [desiredCategory, setDesiredCategory] = useState(domain.desired_category || '')
  const [emailForSubmit, setEmailForSubmit] = useState(domain.email_for_submit || '')
  const [notes, setNotes] = useState(domain.notes || '')
  const [customText, setCustomText] = useState(domain.custom_text || '')

  const categories = ['Business', 'Education', 'Finance', 'Health', 'News', 'Internet']

  const { data: results } = useQuery({
    queryKey: ['domain-results', domain.id],
    queryFn: () => domainsApi.results(domain.id).then(r => r.data),
    refetchInterval: 5000,
  })

  const { data: vendors } = useQuery({
    queryKey: ['vendors'],
    queryFn: () => vendorsApi.list().then(r => r.data),
    staleTime: 60000,
  })

  const checkVendorMutation = useMutation({
    mutationFn: (vendor?: string) => jobsApi.check({ domain_id: domain.id, vendor }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const submitVendorMutation = useMutation({
    mutationFn: (vendor?: string) => jobsApi.submit({ domain_id: domain.id, vendor }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }),
  })

  const reputationMutation = useMutation({
    mutationFn: () => jobsApi.reputation({ domain_id: domain.id }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['domain-results', domain.id] }),
  })

  const saveMutation = useMutation({
    mutationFn: () => domainsApi.update(domain.id, {
      desired_category: desiredCategory || undefined,
      email_for_submit: emailForSubmit || undefined,
      notes: notes || undefined,
      custom_text: customText || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['domains'] })
      queryClient.invalidateQueries({ queryKey: ['domain', domain.id] })
      setEditing(false)
    },
  })

  // Build result lookup by vendor id
  const resultMap: Record<number, any> = {}
  results?.forEach((r: any) => { resultMap[r.vendor_id] = r })

  const categoryVendors = vendors?.filter((v: any) => v.vendor_type === 'category') || []
  const reputationVendors = vendors?.filter((v: any) => v.vendor_type === 'reputation') || []

  return (
    <div className="border-t border-border bg-accent/20 px-4 py-4 space-y-4">
      {/* Config Section */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {editing ? (
            <div className="grid grid-cols-2 gap-3 max-w-2xl">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Desired Category</label>
                <select value={desiredCategory} onChange={e => setDesiredCategory(e.target.value)}
                  className="w-full px-2 py-1.5 rounded border border-input bg-background text-sm">
                  <option value="">None</option>
                  {categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Email for Submissions</label>
                <input type="email" value={emailForSubmit} onChange={e => setEmailForSubmit(e.target.value)}
                  className="w-full px-2 py-1.5 rounded border border-input bg-background text-sm" placeholder="admin@example.com" />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Notes</label>
                <input type="text" value={notes} onChange={e => setNotes(e.target.value)}
                  className="w-full px-2 py-1.5 rounded border border-input bg-background text-sm" placeholder="Notes..." />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Custom Submit Text</label>
                <input type="text" value={customText} onChange={e => setCustomText(e.target.value)}
                  className="w-full px-2 py-1.5 rounded border border-input bg-background text-sm" placeholder="Custom submission text..." />
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-6 text-sm">
              <div><span className="text-muted-foreground">Category:</span> <span className="font-medium">{domain.desired_category || 'Not set'}</span></div>
              <div><span className="text-muted-foreground">Email:</span> <span className="font-medium">{domain.email_for_submit || 'Not set'}</span></div>
              {domain.notes && <div><span className="text-muted-foreground">Notes:</span> <span className="font-medium">{domain.notes}</span></div>}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 ml-4">
          {editing ? (
            <>
              <button onClick={() => saveMutation.mutate()} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium bg-primary text-primary-foreground hover:opacity-90">
                <Save size={12} /> Save
              </button>
              <button onClick={() => setEditing(false)} className="p-1.5 rounded hover:bg-accent"><X size={14} /></button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)} className="flex items-center gap-1 px-2 py-1.5 rounded text-xs border border-border hover:bg-accent">
                <Pencil size={12} /> Edit
              </button>
              <button onClick={() => reputationMutation.mutate()} className="flex items-center gap-1 px-2 py-1.5 rounded text-xs border border-border hover:bg-accent">
                <RefreshCw size={12} /> Reputation
              </button>
              {domain.desired_category && (
                <button onClick={() => submitVendorMutation.mutate()} className="flex items-center gap-1 px-2 py-1.5 rounded text-xs bg-primary text-primary-foreground hover:opacity-90">
                  <Send size={12} /> Submit All
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Category Vendors */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Category Vendors</h4>
        <div className="space-y-1">
          {categoryVendors.map((vendor: any) => {
            const r = resultMap[vendor.id]
            return (
              <div key={vendor.id} className="flex items-center gap-3 px-3 py-2 rounded-md bg-card border border-border">
                <div className="w-40 flex-shrink-0">
                  <span className="text-sm font-medium">{vendor.display_name}</span>
                </div>
                <div className="w-20 flex-shrink-0">
                  <StatusBadge status={r?.status} />
                </div>
                <div className="flex-1 min-w-0">
                  <CategoryBadge category={r?.category} desired={domain.desired_category} />
                </div>
                <div className="text-xs text-muted-foreground w-36 flex-shrink-0 text-right">
                  {r?.completed_at ? new Date(r.completed_at).toLocaleString() : '--'}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button onClick={() => checkVendorMutation.mutate(vendor.name)}
                    className="p-1 rounded hover:bg-accent" title="Re-check this vendor">
                    <RefreshCw size={13} />
                  </button>
                  {vendor.supports_submit && domain.desired_category && (
                    <button onClick={() => submitVendorMutation.mutate(vendor.name)}
                      className="p-1 rounded hover:bg-accent text-primary" title="Submit category to this vendor">
                      <Send size={13} />
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
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Reputation Vendors</h4>
        <div className="space-y-1">
          {reputationVendors.map((vendor: any) => {
            const r = resultMap[vendor.id]
            return (
              <div key={vendor.id} className="flex items-center gap-3 px-3 py-2 rounded-md bg-card border border-border">
                <div className="w-40 flex-shrink-0">
                  <span className="text-sm font-medium">{vendor.display_name}</span>
                </div>
                <div className="w-20 flex-shrink-0">
                  <StatusBadge status={r?.status} />
                </div>
                <div className="flex-1 min-w-0 text-sm text-muted-foreground truncate">
                  {r?.category || r?.reputation || (r?.error_message ? r.error_message.split('\n')[0] : '--')}
                </div>
                <div className="text-xs text-muted-foreground w-36 flex-shrink-0 text-right">
                  {r?.completed_at ? new Date(r.completed_at).toLocaleString() : '--'}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}


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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="w-full max-w-lg bg-card rounded-lg border border-border p-6 shadow-xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-4">Add Domain</h3>

        {error && <div className="p-3 mb-4 rounded-md bg-destructive/10 text-destructive text-sm">{error}</div>}

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Domain *</label>
            <input type="text" value={domain} onChange={e => setDomain(e.target.value)} placeholder="example.com"
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Display Name</label>
            <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="My Website"
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Desired Category</label>
            <select value={category} onChange={e => setCategory(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring">
              <option value="">Select category...</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email for Submissions</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@example.com"
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} placeholder="Optional notes..."
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none" />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent">Cancel</button>
          <button
            onClick={() => mutation.mutate({ domain, display_name: displayName || undefined, desired_category: category || undefined, email_for_submit: email || undefined, notes: notes || undefined })}
            disabled={!domain || mutation.isPending}
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50"
          >
            {mutation.isPending ? 'Adding...' : 'Add Domain'}
          </button>
        </div>
      </div>
    </div>
  )
}
