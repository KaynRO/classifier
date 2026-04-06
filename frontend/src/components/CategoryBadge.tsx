import { cn } from '@/lib/utils'

export default function CategoryBadge({ category, desired }: { category?: string | null; desired?: string | null }) {
  if (!category) return <span className="text-[11px] text-muted-foreground/50">--</span>

  const isMatch = desired && category.toLowerCase().includes(desired.toLowerCase())
  const lower = category.toLowerCase()

  let color = 'bg-secondary/80 text-secondary-foreground'
  if (lower.includes('uncategorized') || lower.includes('not found') || lower.includes('newly observed')) {
    color = 'bg-orange-500/20 text-orange-400'
  } else if (lower.includes('business') || lower.includes('economy')) {
    color = 'bg-blue-500/15 text-blue-400'
  } else if (lower.includes('finance') || lower.includes('financial')) {
    color = 'bg-emerald-500/15 text-emerald-400'
  } else if (lower.includes('education')) {
    color = 'bg-purple-500/15 text-purple-400'
  } else if (lower.includes('health')) {
    color = 'bg-pink-500/15 text-pink-400'
  } else if (lower.includes('news') || lower.includes('media')) {
    color = 'bg-amber-500/15 text-amber-400'
  } else if (lower.includes('technology') || lower.includes('internet') || lower.includes('computer')) {
    color = 'bg-cyan-500/15 text-cyan-400'
  }

  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium', color)}>
      {category}
      {desired && isMatch && <span className="text-emerald-400 ml-0.5">&#10003;</span>}
      {desired && !isMatch && category.toLowerCase() !== 'not found' && <span className="text-red-400 ml-0.5">&#10007;</span>}
    </span>
  )
}
