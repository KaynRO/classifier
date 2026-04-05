import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { domainsApi, jobsApi } from '@/api/client'
import StatusBadge from '@/components/StatusBadge'
import { Plus, Search, Play, Trash2, ExternalLink } from 'lucide-react'

export default function DomainsPage() {
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const bulkCheckMutation = useMutation({
    mutationFn: () => jobsApi.bulkCheck(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

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

      {/* Domains Table */}
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Domain</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Desired Category</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Added</th>
              <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.map((domain: any) => (
              <tr key={domain.id} className="border-b border-border hover:bg-accent/50 transition-colors">
                <td className="px-4 py-3">
                  <button onClick={() => navigate(`/domains/${domain.id}`)} className="font-medium hover:underline">
                    {domain.domain}
                  </button>
                  {domain.display_name && (
                    <p className="text-xs text-muted-foreground">{domain.display_name}</p>
                  )}
                </td>
                <td className="px-4 py-3">
                  {domain.desired_category ? (
                    <span className="px-2 py-0.5 rounded bg-secondary text-xs font-medium">{domain.desired_category}</span>
                  ) : (
                    <span className="text-xs text-muted-foreground">Not set</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={domain.is_active ? 'success' : 'cancelled'} />
                </td>
                <td className="px-4 py-3 text-muted-foreground text-xs">
                  {new Date(domain.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => checkMutation.mutate(domain.id)}
                      className="p-1.5 rounded hover:bg-accent" title="Check all vendors">
                      <Play size={14} />
                    </button>
                    <button onClick={() => navigate(`/domains/${domain.id}`)}
                      className="p-1.5 rounded hover:bg-accent" title="View details">
                      <ExternalLink size={14} />
                    </button>
                    <button onClick={() => deleteMutation.mutate(domain.id)}
                      className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive" title="Delete">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {isLoading && (
              <tr><td colSpan={5} className="px-4 py-12 text-center text-muted-foreground">Loading...</td></tr>
            )}
            {!isLoading && (!data?.items || data.items.length === 0) && (
              <tr><td colSpan={5} className="px-4 py-12 text-center text-muted-foreground">No domains found. Click "Add Domain" to get started.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Add Domain Modal */}
      {showAdd && <AddDomainModal onClose={() => setShowAdd(false)} />}
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
