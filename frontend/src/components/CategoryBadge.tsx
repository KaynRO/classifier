import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .split(/[\s/]+/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// Vendor-failure markers — system errors, not classifications.
const ERROR_KEYWORDS = [
  'captcha failed', 'altcha failed', 'login failed', 'playwright missing',
  'rate limited', 'no key', 'timeout', 'error',
]

// No-info / not-yet-classified states.
const NEUTRAL_KEYWORDS = [
  'not found', 'not rated', 'uncategorized', 'unrated', 'none', 'unknown', 'undetected',
  'newly observed', 'newly registered', 'parked', 'pending',
  'insufficient content', 'no established content',
]

// Reputation severity (used only when no `desired` prop is given — i.e., Safety table).
const MALICIOUS_KEYWORDS = ['malicious', 'phishing', 'malware', 'spam', 'fraud', 'scam', 'botnet', 'ransomware', 'trojan', 'command and control', 'high risk']
const WARN_KEYWORDS = ['suspicious', 'medium risk', 'potentially unwanted', 'questionable']
const CLEAN_KEYWORDS = ['clean', 'minimal risk', 'low risk', 'safe', 'trustworthy']

const COLORS = {
  red:    'bg-red-500/20 text-red-400 border border-red-500/30',
  amber:  'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  green:  'bg-emerald-500/15 text-emerald-400',
  grey:   'bg-secondary/60 text-muted-foreground',
}

function classify(norm: string): 'error' | 'neutral' | 'malicious' | 'warn' | 'clean' | 'classified' {
  if (ERROR_KEYWORDS.some(k => norm.includes(k))) return 'error'
  if (NEUTRAL_KEYWORDS.some(k => norm.includes(k))) return 'neutral'
  if (MALICIOUS_KEYWORDS.some(k => norm.includes(k))) return 'malicious'
  if (WARN_KEYWORDS.some(k => norm.includes(k))) return 'warn'
  if (CLEAN_KEYWORDS.some(k => norm.includes(k))) return 'clean'
  return 'classified'
}

// Tokenize on non-alphanumeric, drop very short tokens (a/an/of/and/etc.).
function tokensOf(s: string): string[] {
  return s.toLowerCase().split(/[^a-z0-9]+/).filter(t => t.length >= 3)
}

// Treat two categories as matching if any token from one shares a common
// prefix with any token from the other. Threshold = first 5 chars (or full
// length if either token is shorter), enough to catch:
//   Finance ↔ Financial Services, Adult ↔ Adult Content,
//   Technology ↔ Technology/Internet, News ↔ News and Media, etc.
function fuzzyMatch(category: string, desired: string): boolean {
  const cTokens = tokensOf(category)
  const dTokens = tokensOf(desired)
  for (const d of dTokens) {
    for (const c of cTokens) {
      const n = Math.min(d.length, c.length, 5)
      if (n >= 3 && d.slice(0, n) === c.slice(0, n)) return true
    }
  }
  return false
}

export default function CategoryBadge({ category, desired }: { category?: string | null; desired?: string | null }) {
  if (!category) return <span className="text-[11px] text-muted-foreground/50">--</span>

  const norm = category.toLowerCase().replace(/[-_]+/g, ' ')
  const display = toTitleCase(category)
  const bucket = classify(norm)
  const isMatch = !!(desired && fuzzyMatch(category, desired))

  let color: string
  let suffix: ReactNode = null

  if (desired) {
    // Category-context: green only when the result matches our desired category.
    if (bucket === 'error') color = COLORS.red
    else if (bucket === 'neutral') color = COLORS.grey
    else if (isMatch) { color = COLORS.green; suffix = <span className="text-emerald-400 ml-0.5">&#10003;</span> }
    else { color = COLORS.amber; suffix = <span className="text-amber-400 ml-0.5">&#10007;</span> }
  } else {
    // Reputation-context: severity-based.
    if (bucket === 'error' || bucket === 'malicious') color = COLORS.red
    else if (bucket === 'warn') color = COLORS.amber
    else if (bucket === 'clean') color = COLORS.green
    else if (bucket === 'neutral') color = COLORS.grey
    else color = COLORS.green
  }

  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium', color)}>
      {display}
      {suffix}
    </span>
  )
}
