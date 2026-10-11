export default function SummaryCard({ index, label, value, detail, tone = 'default' }) {
  return (
    <article className={`summary-metric summary-metric--${tone}`}>
      <div className="summary-meta">
        <span className="summary-index">{index}</span>
        <span>{label}</span>
      </div>
      <strong>{typeof value === 'string' ? value.replaceAll('_', ' ') : value ?? 'UNAVAILABLE'}</strong>
      <small>{typeof detail === 'string' ? detail.replaceAll('_', ' ') : detail ?? '—'}</small>
    </article>
  )
}
