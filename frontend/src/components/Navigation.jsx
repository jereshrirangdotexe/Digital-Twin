export const navigationGroups = [
  { label: 'Monitor', description: 'Understand what is happening', pages: [['overview', 'Overview'], ['live', 'Live Twin'], ['analytics', 'Trends']] },
  { label: 'Investigate', description: 'Follow an indication to its evidence', pages: [['alerts', 'Incident timeline'], ['faults', 'Fault investigation'], ['dna', 'Thermal DNA']] },
  { label: 'Take action', description: 'Explore a response before acting', pages: [['lab', 'What-if & sensor checks'], ['maintenance', 'Maintenance guidance']] },
  { label: 'Data & reports', description: 'Manage sources and share evidence', pages: [['assets', 'Assets'], ['reports', 'Reports']] },
]

export default function Navigation({ page, onChange, sourceMode }) {
  const group = navigationGroups.find(g => g.pages.some(([id]) => id === page)) || navigationGroups[0]
  return (
    <header className="site-nav grouped-nav"><div className="nav-top-row">
      <button className="brand-lockup" type="button" onClick={() => onChange('overview')} aria-label="VoltMind home">
        <span className="brand-grid" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
        </span>
        <span className="brand-copy">
          <strong>VOLTMIND</strong>
          <small>DIGITAL TWIN</small>
        </span>
      </button>

      <nav className="primary-nav" aria-label="Main groups">
        {navigationGroups.map((g) => (
          <button
            key={g.label}
            type="button"
            className={group === g ? 'active' : ''}
            aria-current={group === g ? 'true' : undefined}
            onClick={() => onChange(g.pages[0][0])}
          >
            <span>{g.label}</span>
          </button>
        ))}
      </nav>

      <div className="nav-mode" aria-label="Current data source">
        <span className={`mode-square ${sourceMode === 'LOCAL' ? 'simulation' : 'upload'}`} />
        <span>{sourceMode === 'LOCAL' ? 'LOCAL SCADA' : sourceMode === 'UPLOADED' ? 'UPLOADED DATA' : 'READY TO START'}</span>
      </div>
    </div><div className="nav-sub-row"><span className="group-description">{group.description}</span><nav aria-label={`${group.label} pages`}>{group.pages.map(([id,label]) => <button key={id} type="button" className={id === page ? 'active' : ''} aria-current={id === page ? 'page' : undefined} onClick={() => onChange(id)}>{label}</button>)}</nav></div></header>
  )
}
