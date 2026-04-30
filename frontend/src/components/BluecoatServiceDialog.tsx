'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight, Shield } from 'lucide-react'

// Verbatim from the #selFilteringService dropdown on
// https://sitereview.bluecoat.com/ (probed 2026-04-30, 20 options).
const BLUECOAT_SERVICES = [
  'Symantec Edge SWG',
  'Symantec Cloud SWG',
  'Symantec Unified Agent',
  'Symantec Endpoint Security',
  'Symantec Email Security.Cloud',
  'Symantec Messaging Gateway',
  'Symantec Web Isolation',
  'Symantec Browser Protection',
  'Symantec CacheFlow Appliance',
  'Symantec PacketShaper',
  'Symantec Security Analytics',
  'Symantec SSL Visibility',
  'Norton Safe Web',
  'Norton Core',
  'Norton Mobile',
  'Blue Coat ProxyClient',
  'Global Security One',
  'Zone Labs ZoneAlarm Pro',
  'ZyXEL ZyWall',
  'Other (please specify below)',
] as const

export default function BluecoatServiceDialog({
  context,
  onConfirm,
  onCancel,
}: {
  context: string
  onConfirm: (service: string) => void
  onCancel: () => void
}) {
  const [service, setService] = useState<string>('Symantec Edge SWG')

  return (
    <AnimatePresence>
      <motion.div
        key="backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/60 backdrop-blur-md p-4"
        onClick={onCancel}
      >
        <motion.div
          key="card"
          initial={{ opacity: 0, y: 16, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 320, damping: 28 }}
          onClick={e => e.stopPropagation()}
          className="
            relative w-full max-w-[460px] overflow-hidden rounded-[1.75rem]
            bg-card/95 border border-white/10
            shadow-[0_30px_80px_-30px_rgba(0,0,0,0.55),inset_0_1px_0_rgba(255,255,255,0.08)]
          "
        >
          <div className="pointer-events-none absolute inset-0 rounded-[1.75rem] bg-gradient-to-br from-white/[0.04] via-transparent to-primary/[0.05]" />
          <div className="pointer-events-none absolute -top-24 -right-20 h-64 w-64 rounded-full bg-primary/15 blur-3xl" />

          <div className="relative p-7">
            <div className="flex items-start gap-3 mb-5">
              <motion.div
                animate={{ rotate: [0, -3, 3, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary border border-primary/20"
              >
                <Shield size={18} strokeWidth={1.75} />
              </motion.div>
              <div className="flex-1 min-w-0">
                <h3 className="text-[15px] font-semibold tracking-tight leading-tight">BlueCoat needs a filtering service</h3>
                <p className="mt-1.5 text-[12px] text-muted-foreground leading-snug font-mono">{context}</p>
              </div>
            </div>

            <label className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground/80 block mb-2">Service</label>
            <div className="relative mb-6">
              <select
                value={service}
                onChange={e => setService(e.target.value)}
                className="w-full appearance-none px-4 py-3 pr-10 rounded-xl text-sm bg-zinc-900/40 border border-white/10 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/30 transition-all duration-200 hover:bg-zinc-900/60"
              >
                {BLUECOAT_SERVICES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <div className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/60">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={onCancel}
                className="px-4 py-2 rounded-xl border border-white/10 text-sm font-medium hover:bg-white/[0.04] transition-colors"
              >
                Cancel
              </motion.button>
              <motion.button
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.97, y: 0 }}
                transition={{ type: 'spring', stiffness: 400, damping: 24 }}
                onClick={() => onConfirm(service)}
                className="group relative px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_8px_22px_-10px_hsl(var(--primary)/0.6)] flex items-center gap-1.5"
              >
                Submit
                <ArrowRight size={14} strokeWidth={2} className="transition-transform duration-300 group-hover:translate-x-0.5" />
              </motion.button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
