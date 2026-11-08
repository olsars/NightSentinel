import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Bell,
  CheckCircle2, Clock3, Crosshair, Database, Eye, RefreshCw,
  Shield, ShieldAlert, ShieldCheck, Wifi, WifiOff, Zap,
} from 'lucide-react'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const EVENT_POLL_MS = 5000
const HEALTH_POLL_MS = 15000

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    month: 'short', day: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).format(date)
}

function relativeTime(value) {
  if (!value) return 'Time unavailable'
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (!Number.isFinite(seconds)) return formatTime(value)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function PriorityPill({ priority }) {
  const high = String(priority).toLowerCase() === 'high'
  return <span className={`priority-pill ${high ? 'priority-high' : 'priority-low'}`}>
    <span className="priority-dot" />{String(priority || 'unknown').toUpperCase()}
  </span>
}

function EventType({ type }) {
  const restricted = type === 'restricted_zone_entry'
  return <span className={`event-type ${restricted ? 'event-restricted' : 'event-person'}`}>
    {restricted ? <ShieldAlert size={14} /> : <Eye size={14} />}
    {restricted ? 'Restricted zone entry' : 'Person detected'}
  </span>
}

function StatCard({ label, value, detail, icon: Icon, tone = 'neutral' }) {
  return <article className="stat-card">
    <div className="stat-topline">
      <span className="stat-label">{label}</span>
      <span className={`stat-icon ${tone}`}><Icon size={18} /></span>
    </div>
    <div className="stat-value">{value}</div>
    <div className="stat-detail">{detail}</div>
  </article>
}

function App() {
  const [events, setEvents] = useState([])
  const [health, setHealth] = useState('checking')
  const [eventsState, setEventsState] = useState('loading')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [error, setError] = useState('')
  const [now, setNow] = useState(Date.now())

  const fetchHealth = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/health`)
      if (!response.ok) throw new Error(`Health check returned ${response.status}`)
      const data = await response.json()
      setHealth(data?.status === 'online' && data?.service === 'NightSentinel' ? 'online' : 'unknown')
    } catch {
      setHealth('offline')
    }
  }, [])

  const fetchEvents = useCallback(async (manual = false) => {
    try {
      const response = await fetch(`${API_BASE}/events`)
      if (!response.ok) throw new Error(`Events request returned ${response.status}`)
      const data = await response.json()
      if (!Array.isArray(data)) throw new Error('The API response was not an event array.')
      setEvents(data)
      setEventsState(data.length ? 'loaded' : 'empty')
      setError('')
      setLastUpdated(new Date())
    } catch (err) {
      setEventsState('error')
      setError(err.message || 'Unable to reach the events endpoint.')
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    fetchEvents()
    const healthTimer = window.setInterval(fetchHealth, HEALTH_POLL_MS)
    const eventsTimer = window.setInterval(() => fetchEvents(), EVENT_POLL_MS)
    const clockTimer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => {
      window.clearInterval(healthTimer)
      window.clearInterval(eventsTimer)
      window.clearInterval(clockTimer)
    }
  }, [fetchHealth, fetchEvents])

  const highPriority = useMemo(() => events.filter(e => String(e.priority).toLowerCase() === 'high').length, [events])
  const peopleDetected = useMemo(() => events.filter(e => e.event_type === 'person_detected').length, [events])
  const restrictedEntries = useMemo(() => events.filter(e => e.event_type === 'restricted_zone_entry').length, [events])
  const newestEvent = events[0]

  const refresh = () => {
    fetchEvents(true)
    fetchHealth()
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"><Shield size={22} strokeWidth={2.2} /></div>
        <div><div className="brand-name">NIGHT<span>SENTINEL</span></div><div className="brand-sub">SECURITY OPERATIONS</div></div>
      </div>

      <div className="sidebar-section-label">MONITORING</div>
      <div className="nav-item active"><Activity size={17} /><span>Event overview</span><span className="nav-indicator" /></div>
      <div className="nav-item muted"><Crosshair size={17} /><span>Detection feed</span></div>
      <div className="nav-item muted"><Database size={17} /><span>Event records</span></div>

      <div className="sidebar-bottom">
        <div className="system-card">
          <div className="system-card-head"><span className="system-pulse" /> SYSTEM STATUS</div>
          <div className="system-card-status">{health === 'online' ? 'All systems operational' : health === 'checking' ? 'Checking connection' : health === 'unknown' ? 'Unexpected response' : 'API connection lost'}</div>
          <div className="system-card-foot">API · {API_BASE}</div>
        </div>
        <div className="sidebar-footer"><span> NIGHT SENTINEL</span><span>v0.1.0</span></div>
      </div>
    </aside>

    <main className="main-content">
      <header className="topbar">
        <div className="breadcrumb"><span>MONITORING</span><span className="crumb-slash">/</span><strong>EVENT OVERVIEW</strong></div>
        <div className="topbar-right">
          <div className="top-clock"><Clock3 size={14} /><span>{new Date(now).toLocaleTimeString()}</span></div>
          <div className={`connection-chip ${health}`}><span className="connection-dot" />{health === 'online' ? 'API CONNECTED' : health === 'checking' ? 'CONNECTING' : health === 'unknown' ? 'API UNKNOWN' : 'API OFFLINE'}</div>
          <div className="avatar"><ShieldCheck size={17} /></div>
        </div>
      </header>

      <section className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> LIVE SURVEILLANCE SYSTEM</div>
          <h1>Event <span>Overview</span></h1>
          <p className="page-description">Monitor detections and restricted-zone activity across your secured environment.</p>
        </div>
        <button className="refresh-button" onClick={refresh}><RefreshCw size={15} /> Refresh feed</button>
      </section>

      <section className="status-banner">
        <div className="status-banner-icon">{health === 'online' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}</div>
        <div className="status-banner-copy">
          <strong>{health === 'online' ? 'Backend connection established' : health === 'checking' ? 'Checking backend connection' : 'Backend connection unavailable'}</strong>
          <span>{health === 'online' ? 'NightSentinel API is responding to health checks.' : 'Confirm the API is running and VITE_API_BASE_URL points to the correct host.'}</span>
        </div>
        <span className="status-banner-end">{health === 'online' ? 'HEALTHY' : 'CHECK CONNECTION'}</span>
      </section>

      <section className="stats-grid">
        <StatCard label="EVENTS RECEIVED" value={events.length} detail="Latest 100 events from API" icon={Activity} tone="blue" />
        <StatCard label="HIGH PRIORITY" value={highPriority} detail="Restricted-zone alerts" icon={AlertTriangle} tone="red" />
        <StatCard label="PERSON DETECTIONS" value={peopleDetected} detail="Person detected events" icon={Eye} tone="cyan" />
        <StatCard label="ZONE ENTRIES" value={restrictedEntries} detail="Restricted-zone entry events" icon={Zap} tone="amber" />
      </section>

      <section className="content-grid">
        <div className="panel events-panel">
          <div className="panel-header">
            <div><div className="panel-title"><span className="live-indicator" /> EVENT ACTIVITY</div><div className="panel-subtitle">Most recent security events</div></div>
            <div className="feed-meta"><span className="feed-live">LIVE FEED</span><span className="feed-count">{events.length} / 100</span></div>
          </div>
          {eventsState === 'error' && <div className="inline-alert"><WifiOff size={17} /><div><strong>Unable to load events</strong><span>{error} Check that the backend is running and accessible.</span></div></div>}
          {eventsState === 'loading' && <div className="empty-state"><RefreshCw className="empty-icon spin" size={25} /><strong>Connecting to event stream</strong><span>Waiting for the NightSentinel API…</span></div>}
          {eventsState === 'empty' && <div className="empty-state"><ShieldCheck className="empty-icon" size={27} /><strong>No events recorded</strong><span>New detections will appear here as they are received.</span></div>}
          {events.length > 0 && <div className="event-list">
            {events.map((event) => <article className="event-row" key={event.id}>
              <div className={`event-symbol ${event.priority === 'high' ? 'danger' : 'calm'}`}>
                {event.priority === 'high' ? <ShieldAlert size={18} /> : <Eye size={18} />}
              </div>
              <div className="event-main">
                <div className="event-main-top"><EventType type={event.event_type} /><PriorityPill priority={event.priority} /></div>
                <div className="event-details"><span><Crosshair size={12} /> Zone: <strong>{event.zone || 'Unspecified'}</strong></span><span>Track ID: <strong>{event.track_id || '—'}</strong></span></div>
              </div>
              <div className="event-time"><strong>{relativeTime(event.timestamp)}</strong><span>{formatTime(event.timestamp)}</span></div>
            </article>)}
          </div>}
          <div className="panel-footer"><span><span className="footer-dot" /> POLLING EVERY 5 SECONDS</span><span>Newest events shown first</span></div>
        </div>

        <div className="right-column">
          <section className="panel alert-panel">
            <div className="panel-header compact"><div><div className="panel-title">PRIORITY SNAPSHOT</div><div className="panel-subtitle">Current event breakdown</div></div><ShieldAlert size={17} className="panel-header-icon" /></div>
            <div className="priority-total"><strong>{highPriority}</strong><span>HIGH PRIORITY<br />EVENTS</span></div>
            <div className="priority-bar"><div className="priority-bar-high" style={{ width: `${events.length ? highPriority / events.length * 100 : 0}%` }} /></div>
            <div className="priority-legend"><span><i className="legend-red" /> High priority <strong>{highPriority}</strong></span><span><i className="legend-blue" /> Low priority <strong>{events.length - highPriority}</strong></span></div>
          </section>

          <section className="panel latest-panel">
            <div className="panel-header compact"><div><div className="panel-title">LATEST ACTIVITY</div><div className="panel-subtitle">Most recent event received</div></div><Bell size={17} className="panel-header-icon" /></div>
            {newestEvent ? <div className="latest-event">
              <div className={`latest-event-icon ${newestEvent.priority === 'high' ? 'danger' : 'calm'}`}>{newestEvent.priority === 'high' ? <ShieldAlert size={20} /> : <Eye size={20} />}</div>
              <div className="latest-event-type">{newestEvent.event_type === 'restricted_zone_entry' ? 'Restricted zone entry' : 'Person detected'}</div>
              <PriorityPill priority={newestEvent.priority} />
              <div className="latest-info"><span>ZONE</span><strong>{newestEvent.zone || 'Unspecified'}</strong></div>
              <div className="latest-info"><span>TRACK ID</span><strong>{newestEvent.track_id || '—'}</strong></div>
              <div className="latest-time"><Clock3 size={13} />{formatTime(newestEvent.timestamp)}</div>
            </div> : <div className="latest-placeholder">No recent activity to display.</div>}
          </section>

          <section className="api-card">
            <div className="api-card-head"><Wifi size={15} /><span>API CONNECTION</span><span className={`api-state ${health}`}>{health.toUpperCase()}</span></div>
            <div className="api-endpoint"><span>BASE URL</span><strong>{API_BASE}</strong></div>
            <div className="api-endpoint"><span>LAST EVENT SYNC</span><strong>{lastUpdated ? lastUpdated.toLocaleTimeString() : 'Not synced yet'}</strong></div>
            <div className="api-foot"><span className="api-foot-dot" /> GET /events <span className="api-foot-separator">·</span> GET /health</div>
          </section>
        </div>
      </section>

      <footer className="page-footer"><span>© {new Date().getFullYear()} NIGHT SENTINEL</span><span>SECURITY EVENT MONITORING <i /> BUILT FOR SITUATIONAL AWARENESS</span></footer>
    </main>
  </div>
}

export default App