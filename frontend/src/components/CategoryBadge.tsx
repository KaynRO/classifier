import { cn } from '@/lib/utils'

const categoryColors: Record<string, string> = {
  business: 'bg-blue-500/15 text-blue-700 dark:text-blue-400',
  education: 'bg-purple-500/15 text-purple-700 dark:text-purple-400',
  finance: 'bg-green-500/15 text-green-700 dark:text-green-400',
  health: 'bg-pink-500/15 text-pink-700 dark:text-pink-400',
  news: 'bg-orange-500/15 text-orange-700 dark:text-orange-400',
  internet: 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-400',
}

export default function CategoryBadge({ category, desired }: { category?: string | null; desired?: string | null }) {
  if (!category) return <span className="text-xs text-muted-foreground">--</span>

  const isMatch = desired && category.toLowerCase().includes(desired.toLowerCase())
  const colorKey = Object.keys(categoryColors).find(k => category.toLowerCase().includes(k))

  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
      colorKey ? categoryColors[colorKey] : 'bg-secondary text-secondary-foreground',
      desired && !isMatch && 'ring-1 ring-red-500/50'
    )}>
      {category}
      {desired && isMatch && <span className="text-emerald-500">&#10003;</span>}
      {desired && !isMatch && <span className="text-red-500">&#10007;</span>}
    </span>
  )
}
