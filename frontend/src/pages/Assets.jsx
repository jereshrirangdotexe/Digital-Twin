import StatusPill from '../components/StatusPill'

export default function Assets({ assets, current, onOpenAsset }) {
  return (
    <div className="editorial-page assets-page">
      <section className="light-section section-frame assets-hero">
        <div className="hero-kicker-row">
          <span>(01) ASSET REGISTRY</span>
          <span>{assets.length} TRANSFORMERS CONFIGURED</span>
        </div>
        <h1 className="display-title">TRANSFORMER<br />INDEX.</h1>
        <p className="hero-intro">A compact engineering index. Open a row for model, calibration and commissioning details.</p>
      </section>

      <section className="light-section section-frame asset-index-section">
        <div className="asset-registry-list">
          {assets.map((asset, index) => {
            const selected = current?.asset?.id === asset.id
            return (
              <details className={`registry-row ${selected ? 'selected' : ''}`} key={asset.id}>
                <summary>
                  <span className="registry-index">0{index + 1}.</span>
                  <strong>{asset.id}</strong>
                  <span>{asset.ratingKVA} kVA</span>
                  <span>{asset.location || 'LOCATION UNAVAILABLE'}</span>
                  {selected ? <StatusPill tone="info">SELECTED</StatusPill> : <span />}
                  <span className="detail-plus">+</span>
                </summary>
                <div className="registry-expanded">
                  <div className="asset-meta-grid">
                    <div><span>NOMINAL VOLTAGE</span><strong>{asset.nominalVoltage ?? 'UNAVAILABLE'} V</strong></div>
                    <div><span>RATED CURRENT</span><strong>{asset.ratedCurrent ?? 'UNAVAILABLE'} A</strong></div>
                    <div><span>COOLING</span><strong>{asset.coolingType || 'UNAVAILABLE'}</strong></div>
                    <div><span>SAMPLING</span><strong>{asset.samplingInterval}</strong></div>
                    <div><span>ML MODEL</span><strong>{asset.modelVersion}</strong></div>
                    <div><span>DIGITAL TWIN</span><strong>{asset.digitalTwinVersion}</strong></div>
                    <div><span>CALIBRATION</span><strong>{asset.calibrationStatus}</strong></div>
                    <div><span>LAST CALIBRATION</span><strong>{asset.lastCalibration || 'UNAVAILABLE'}</strong></div>
                  </div>
                  <button type="button" className="text-button" onClick={() => onOpenAsset(asset.id)}>
                    OPEN LIVE TWIN ↘
                  </button>
                </div>
              </details>
            )
          })}
        </div>
      </section>

      <section className="dark-section section-frame sensor-health-section">
        <div className="section-title-row dark">
          <span>(02)</span>
          <div>
            <p className="section-kicker">DATA QUALITY / SYSTEM STATUS</p>
            <h2>CURRENT CHANNEL HEALTH</h2>
          </div>
        </div>

        <div className="sensor-index">
          {[
            ['01', 'VOLTAGE SENSORS', current?.telemetry?.voltageR != null && current?.telemetry?.voltageY != null && current?.telemetry?.voltageB != null],
            ['02', 'CURRENT SENSORS', current?.telemetry?.currentR != null && current?.telemetry?.currentY != null && current?.telemetry?.currentB != null],
            ['03', 'OIL TEMPERATURE', current?.telemetry?.topOilTempC != null],
            ['04', 'AMBIENT TEMPERATURE', current?.telemetry?.ambientTempC != null],
            ['05', 'COMMUNICATION LINK', current?.telemetry?.communicationAvailable === true],
          ].map(([index, label, ok]) => (
            <div className="sensor-row" key={index}>
              <span>{index}</span>
              <strong>{label}</strong>
              <StatusPill tone={ok ? (current?.ml?.assetCondition === 'SENSOR_SUSPECT' ? 'warning' : 'info') : 'danger'}>{ok ? (current?.ml?.assetCondition === 'SENSOR_SUSPECT' ? 'CHECK QUALITY ISSUES' : 'AVAILABLE') : 'UNAVAILABLE'}</StatusPill>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
