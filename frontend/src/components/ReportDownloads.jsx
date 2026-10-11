import { createReport, readingsCsv, reportHtml, download } from '../services/report'

export default function ReportDownloads({ history, alerts }) {
  const exportReport = (format) => {
    const report = createReport(history, alerts), name = `VoltMind_${report.asset.replace(/[^a-zA-Z0-9_-]/g, '_')}_${report.replay.processedRows}`
    if (format === 'csv') download(readingsCsv(history), `${name}_readings.csv`, 'text/csv;charset=utf-8')
    else if (format === 'json') download(JSON.stringify(report, null, 2), `${name}_summary.json`, 'application/json')
    else download(reportHtml(report), `${name}_report.html`, 'text/html;charset=utf-8')
  }
  return <section className="report-downloads" aria-label="Monitoring report downloads">
    <div><span className="section-kicker">REPORTING</span><p>Download this session’s retained readings, published assessments and alerts. Reports include coverage, trends and limitations.</p></div>
    <button disabled={!history.length} onClick={() => exportReport('csv')}>Download readings CSV</button>
    <button disabled={!history.length} onClick={() => exportReport('json')}>Download summary JSON</button>
    <button disabled={!history.length} onClick={() => exportReport('html')}>Download printable report</button>
    <small>Open the HTML report and use Print / Save as PDF. Exports reflect processed rows, not unread data.</small>
  </section>
}
