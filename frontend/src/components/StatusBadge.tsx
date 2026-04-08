import { cn } from '@/lib/utils'
import { Loader2, X } from 'lucide-react'

const styles: Record<string, string> = {
  clean: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  running: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  submitted: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  uncategorized: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  cancelled: 'bg-neutral-500/20 text-neutral-400 border-neutral-500/30',
}

// Standardized Title Case labels
const labels: Record<string, string> = {
  clean: 'Clean',
  success: 'Clean',
  completed: 'Completed',
  failed: 'Failed',
  error: 'Error',
  running: 'Running',
  pending: 'Pending',
  submitted: 'Submitted',
  uncategorized: 'Uncategorized',
  cancelled: 'Cancelled',
}

interface Props {
  status: string | null | undefined
  loading?: boolean
  onCancel?: () => void
}

export default function StatusBadge({ status, loading, onCancel }: Props) {
  const isRunning = loading || status === 'running' || status === 'pending'

  if (isRunning) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-sky-500/20 text-sky-400 border border-sky-500/30">
        <Loader2 size={10} className="animate-spin" />
        Running
        {onCancel && (
          <button
            onClick={(e) => { e.stopPropagation(); onCancel() }}
            className="ml-0.5 -mr-0.5 hover:bg-sky-500/30 rounded-full p-0.5 transition-colors"
            title="Cancel"
          >
            <X size={10} />
          </button>
        )}
      </span>
    )
  }
  if (!status) return <span className="text-[11px] text-muted-foreground/50">--</span>
  const label = labels[status] || status.charAt(0).toUpperCase() + status.slice(1)
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border',
      styles[status] || styles.pending
    )}>
      {label}
    </span>
  )
}
