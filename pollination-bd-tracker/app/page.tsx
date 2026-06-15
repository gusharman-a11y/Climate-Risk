import { unstable_cache } from 'next/cache'
import { getHotSheet } from '@/lib/data'
import HotSheetClient from '@/components/HotSheetClient'

export const dynamic = 'force-dynamic'

const getCachedHotSheet = unstable_cache(
  getHotSheet,
  ['hot-sheet'],
  { revalidate: 120 },
)

export default async function HotSheetPage() {
  const { main, sbtiV2 } = await getCachedHotSheet()
  return <HotSheetClient companies={main} sbtiV2Companies={sbtiV2} />
}
