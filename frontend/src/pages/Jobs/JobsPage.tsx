import { useQuery } from '@tanstack/react-query'
import { jobsApi } from '@/api/client'
import { useWebSocket } from '@/context/WebSocketContext'
import StatusBadge from '@/components/StatusBadge'

export default function JobsPage() {
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
        <p className="text-muted-foreground mt-1">Track vendor check and submission operations</p>
      </div>

      {/* Active Updates */}
      {messages.length > 0 && (
        <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-4">
          <h3 className="font-semibold text-sm mb-2">Live Updates</h3>
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {messages.slice(0, 8).map((msg, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <StatusBadge status={msg.status} />
                <span className="font-medium">{msg.vendor}</span>
                {msg.category && <span className="text-muted-foreground">{msg.category}</span>}
                {msg.error && <span className="text-red-500 text-xs truncate max-w-xs">{msg.error}</span>}
                <span className="text-xs text-muted-foreground ml-auto">{new Date(msg.timestamp).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Jobs Table */}
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Job ID</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Action</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Vendor</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Progress</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Requested</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.map((job: any) => {
              const progress = job.progress || {}
              const total = Object.keys(progress).length
              const done = Object.values(progress).filter((s: any) => s === 'success' || s === 'failed').length

              return (
                <tr key={job.id} className="border-b border-border hover:bg-accent/50">
                  <td className="px-4 py-3 font-mono text-xs">{job.id.slice(0, 8)}...</td>
                  <td className="px-4 py-3 capitalize">{job.action_type}</td>
                  <td className="px-4 py-3">{job.vendor_filter || 'All'}</td>
                  <td className="px-4 py-3"><StatusBadge status={job.status} /></td>
                  <td className="px-4 py-3">
                    {total > 0 ? (
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 transition-all"
                            style={{ width: `${(done / total) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">{done}/{total}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">--</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(job.requested_at).toLocaleString()}
                  </td>
                </tr>
              )
            })}
            {isLoading && (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">Loading...</td></tr>
            )}
            {!isLoading && (!data?.items || data.items.length === 0) && (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">No jobs yet. Trigger a check from the Domains page.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
