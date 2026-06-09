export default function Loading() {
  return (
    <div>
      {/* Page header skeleton */}
      <div className="bg-white border-b border-[#e6e9ef] px-6 py-3 flex items-center justify-between sticky top-14 z-10">
        <div className="h-5 w-24 bg-[#f6f7fb] rounded animate-pulse" />
        <div className="flex gap-2">
          <div className="h-8 w-40 bg-[#f6f7fb] rounded animate-pulse" />
          <div className="h-8 w-32 bg-[#f6f7fb] rounded animate-pulse" />
        </div>
      </div>

      {/* Column headers skeleton */}
      <div className="bg-[#f6f7fb] border-b border-[#e6e9ef] px-6 py-2 flex gap-6">
        {['Company', 'Score', 'ASRS Group', 'Top Signal', 'Sector', 'Relationship'].map(h => (
          <div key={h} className="h-3 bg-[#e6e9ef] rounded w-16 animate-pulse" />
        ))}
      </div>

      {/* Group headers + rows skeleton */}
      {[1, 2, 3].map(g => (
        <div key={g}>
          <div className="bg-white border-b border-[#e6e9ef] px-6 py-2 flex items-center gap-3"
            style={{ borderLeft: '3px solid #e6e9ef' }}>
            <div className="w-2.5 h-2.5 rounded-full bg-[#e6e9ef] animate-pulse" />
            <div className="h-4 w-20 bg-[#f6f7fb] rounded animate-pulse" />
            <div className="h-3 w-36 bg-[#f6f7fb] rounded animate-pulse" />
          </div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-white border-b border-[#e6e9ef] px-6 py-3 flex gap-6 items-center"
              style={{ borderLeft: '3px solid #f6f7fb' }}>
              <div className="flex-1 space-y-1.5">
                <div className="h-4 w-48 bg-[#f6f7fb] rounded animate-pulse" />
                <div className="h-3 w-12 bg-[#f6f7fb] rounded animate-pulse" />
              </div>
              <div className="h-5 w-12 bg-[#f6f7fb] rounded-full animate-pulse" />
              <div className="h-5 w-16 bg-[#f6f7fb] rounded-full animate-pulse" />
              <div className="flex-1 h-3 bg-[#f6f7fb] rounded animate-pulse" />
              <div className="w-24 h-3 bg-[#f6f7fb] rounded animate-pulse" />
              <div className="h-5 w-20 bg-[#f6f7fb] rounded-full animate-pulse" />
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
