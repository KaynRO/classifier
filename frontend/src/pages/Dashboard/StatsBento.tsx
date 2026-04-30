'use client'
import { memo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Globe, Shield, AlertTriangle, Clock, ArrowUpRight } from 'lucide-react'

const SPRING = { type: 'spring' as const, stiffness: 110, damping: 22 }

function fmt(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') return v.toLocaleString('en-US')
  return String(v)
}

interface StatsBentoProps {
  activeDomains?: number
  totalVendors?: number
  mismatches?: number
  pendingJobs?: number
}

function StatsBentoImpl({
  activeDomains,
  totalVendors,
  mismatches,
  pendingJobs,
}: StatsBentoProps) {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } },
      }}
      className="
        grid gap-4
        grid-cols-1
        md:grid-cols-2
        lg:grid-cols-4 lg:auto-rows-[148px]
      "
    >
      <motion.div
        variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: SPRING } }}
        className="lg:col-span-2 lg:row-span-2"
      >
        <Link
          to="/domains"
          className="
            group relative h-full block overflow-hidden rounded-3xl
            border border-white/10 bg-card/80
            shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_24px_60px_-30px_rgba(0,0,0,0.45)]
            hover:border-primary/30 transition-colors
          "
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/[0.10] via-transparent to-transparent" />
          <div className="pointer-events-none absolute -bottom-20 -right-12 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />

          <motion.div
            aria-hidden
            animate={{ rotate: 360 }}
            transition={{ duration: 32, repeat: Infinity, ease: 'linear' }}
            className="pointer-events-none absolute -top-16 -right-16 h-56 w-56 rounded-full border border-dashed border-primary/15"
          />

          <div className="relative flex h-full flex-col justify-between p-7">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/70">
                  Active domains
                </p>
                <div className="mt-1 inline-flex items-center gap-2 text-[11px] text-emerald-400/90">
                  <span className="relative inline-flex h-1.5 w-1.5">
                    <motion.span
                      animate={{ scale: [1, 2, 1], opacity: [0.6, 0, 0.6] }}
                      transition={{ duration: 2, repeat: Infinity, ease: 'easeOut' }}
                      className="absolute inset-0 rounded-full bg-emerald-400"
                    />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  </span>
                  Streaming
                </div>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/12 border border-primary/20 text-primary">
                <Globe size={18} strokeWidth={1.75} />
              </div>
            </div>

            <div>
              <div className="flex items-baseline gap-3">
                <span className="text-7xl md:text-8xl font-semibold tracking-tighter leading-none tabular-nums">
                  {fmt(activeDomains)}
                </span>
                <span className="text-sm text-muted-foreground translate-y-[-0.4em]">
                  monitored
                </span>
              </div>
              <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-primary transition-colors">
                Explore the catalog
                <ArrowUpRight size={13} className="transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
            </div>
          </div>
        </Link>
      </motion.div>

      <motion.div
        variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: SPRING } }}
        className="
          relative overflow-hidden rounded-3xl border border-white/10 bg-card/70
          p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]
        "
      >
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/70">
            Vendors
          </p>
          <Shield size={15} strokeWidth={1.75} className="text-emerald-400/80" />
        </div>
        <p className="mt-4 text-4xl font-semibold tabular-nums tracking-tighter">
          {fmt(totalVendors)}
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">Categorization + reputation</p>
      </motion.div>

      <motion.div
        variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: SPRING } }}
        className="
          relative overflow-hidden rounded-3xl border border-amber-500/15 bg-gradient-to-br from-amber-500/[0.05] via-card/70 to-card/70
          p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]
        "
      >
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/70">
            Mismatches
          </p>
          <motion.div
            animate={mismatches && mismatches > 0 ? { y: [0, -1.5, 0] } : {}}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            className="text-amber-500/90"
          >
            <AlertTriangle size={15} strokeWidth={1.75} />
          </motion.div>
        </div>
        <p className="mt-4 text-4xl font-semibold tabular-nums tracking-tighter">
          {fmt(mismatches)}
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {mismatches && mismatches > 0 ? 'Need attention' : 'All aligned'}
        </p>
      </motion.div>

      <motion.div
        variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: SPRING } }}
        className="
          lg:col-span-2 relative overflow-hidden rounded-3xl
          border border-white/10 bg-card/70
          p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]
        "
      >
        {(pendingJobs ?? 0) > 0 && (
          <motion.div
            aria-hidden
            initial={{ x: '-100%' }}
            animate={{ x: '100%' }}
            transition={{ duration: 2.4, repeat: Infinity, ease: 'linear' }}
            className="pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-white/[0.04] to-transparent"
          />
        )}

        <div className="relative flex items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/70">
                Pending jobs
              </p>
              {(pendingJobs ?? 0) > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 px-1.5 py-px text-[9px] font-medium uppercase tracking-wider">
                  <motion.span
                    animate={{ scale: [1, 1.5, 1] }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
                    className="inline-block h-1 w-1 rounded-full bg-sky-400"
                  />
                  Live
                </span>
              )}
            </div>
            <p className="mt-3 text-5xl font-semibold tabular-nums tracking-tighter">
              {fmt(pendingJobs)}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Workers are processing in parallel
            </p>
          </div>
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Clock size={18} strokeWidth={1.75} />
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

const StatsBento = memo(StatsBentoImpl)
export default StatsBento
