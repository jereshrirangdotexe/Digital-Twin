export default function StatusPill({ children, tone = 'neutral' }) {
  return <span className={`status-pill status-pill--${tone}`}>{typeof children === 'string' ? children.replaceAll('_', ' ') : children ?? '—'}</span>
}
