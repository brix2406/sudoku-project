function StatusBadge({ status }) {
  const normalized = (status || 'offline').toLowerCase();
  return <span className={`status-badge ${normalized}`}>{normalized}</span>;
}

function StatusSection({ heartbeat, isLoading, error }) {
  const statusValue = heartbeat?.serviceStatus || (isLoading ? 'loading' : 'offline');

  return (
    <section id="status" className="page-section status-section">
      <div className="section-inner">
        <h2>Worker Status (Work In Progress)</h2>
        <p className="section-copy">
          Heartbeat is polled automatically. Right now it runs in mock mode until backend `/status` is available.
        </p>

        <div className="status-panel">
          <p>
            Service: <StatusBadge status={statusValue} />
          </p>
          <p>Worker connection: {heartbeat?.workerStatus || 'pending'}</p>
          <p>Heartbeat latency: {heartbeat?.latencyMs ?? 'n/a'} ms</p>
          <p>Queue depth: {heartbeat?.queueDepth ?? 'n/a'}</p>
          <p>Updated: {heartbeat?.timestamp ? new Date(heartbeat.timestamp).toLocaleTimeString() : 'n/a'}</p>
        </div>

        {error && <p className="error-text">{error}</p>}
      </div>
    </section>
  );
}

export default StatusSection;
