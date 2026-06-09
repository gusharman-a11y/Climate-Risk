import { getHotSheet } from '@/lib/data'
import HotSheetClient from '@/components/HotSheetClient'

import { unstable_cache } from 'next/cache'

const getCachedHotSheet = unstable_cache(
  getHotSheet,
  ['hot-sheet'],
  { revalidate: 120 }, // cache for 2 minutes
)

export default async function HotSheetPage() {
  const companies = await getCachedHotSheet()
  return <HotSheetClient companies={companies} />
}
