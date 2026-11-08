const signalIntro = document.querySelector("#signal-intro");
const skipIntro = document.querySelector("#skip-intro");
const cameraFeed = document.querySelector("#camera-feed");
const cameraFrame = document.querySelector("#camera-frame");
const cameraStatus = document.querySelector("#camera-status");
const cameraPlaceholder = document.querySelector("#camera-placeholder");
const apiState = document.querySelector("#api-state");
const streamState = document.querySelector("#stream-state");
const overallStatus = document.querySelector("#overall-status");
const eventsBody = document.querySelector("#events-body");
const refreshButton = document.querySelector("#refresh-button");

let introDismissed = false;

function dismissIntro() {
  if (introDismissed) return;
  introDismissed = true;
  signalIntro.classList.add("is-leaving");
  document.documentElement.classList.remove("intro-pending");
  window.setTimeout(() => {
    signalIntro.hidden = true;
  }, 750);
}

skipIntro.addEventListener("click", dismissIntro);
window.setTimeout(
  dismissIntro,
  window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 150 : 2600,
);

const jetsonHost = window.location.hostname;
const cameraBaseUrl = `${window.location.protocol}//${jetsonHost}:8080`;
document.querySelector("#camera-address").textContent = `${jetsonHost}:8080`;

function setState(element, state, label) {
  element.dataset.state = state;
  element.textContent = label;
}

function setPillState(element, state, label) {
  element.dataset.state = state;
  const labelElement = element.querySelector("span:last-child");
  if (labelElement) labelElement.textContent = label;
}

function titleCase(value) {
  return String(value || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatTimestamp(timestamp, includeDate = true) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return new Intl.DateTimeFormat(undefined, {
    ...(includeDate ? { month: "short", day: "numeric" } : {}),
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function updateClock() {
  const now = new Date();
  document.querySelector("#current-date").textContent = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(now);
  document.querySelector("#current-time").textContent = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(now);
}

async function refreshHealth() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    await response.json();
    setState(apiState, "online", "Online");
    setPillState(overallStatus, "online", "System online");
  } catch (_error) {
    setState(apiState, "offline", "Offline");
    setPillState(overallStatus, "error", "API unavailable");
  }
}

async function refreshCameraStatus() {
  try {
    const response = await fetch(`${cameraBaseUrl}/healthz`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    setState(streamState, "online", "Online");
    setPillState(cameraStatus, "online", "Live feed");
    if (!cameraFeed.src) cameraFeed.src = `${cameraBaseUrl}/stream.mjpg`;
    cameraFrame.classList.add("has-feed");
  } catch (_error) {
    setState(streamState, "offline", "Offline");
    setPillState(cameraStatus, "offline", "Feed offline");
    cameraFrame.classList.remove("has-feed");
  }
}

function makeCell(text, className = "") {
  const span = document.createElement("span");
  span.textContent = text;
  if (className) span.className = className;
  return span;
}

function renderEvents(events) {
  document.querySelector("#event-count").textContent = String(events.length);
  if (!events.length) return;

  const latest = events[0];
  document.querySelector("#latest-event-type").textContent = titleCase(latest.event_type);
  document.querySelector("#latest-event-time").textContent = formatTimestamp(latest.timestamp);
  document.querySelector("#latest-zone").textContent = titleCase(latest.zone);
  document.querySelector("#latest-track").textContent = latest.track_id;

  const fragment = document.createDocumentFragment();
  for (const event of events.slice(0, 12)) {
    const row = document.createElement("div");
    row.className = "event-row";
    const priority = makeCell(
      titleCase(event.priority),
      `priority ${event.priority === "high" ? "high" : ""}`.trim(),
    );
    row.append(
      makeCell(titleCase(event.event_type), "event-name"),
      makeCell(titleCase(event.zone)),
      makeCell(event.track_id),
      priority,
      makeCell(formatTimestamp(event.timestamp), "event-time"),
    );
    fragment.append(row);
  }
  eventsBody.replaceChildren(fragment);
}

async function refreshEvents() {
  refreshButton.disabled = true;
  try {
    const response = await fetch("/events", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderEvents(await response.json());
    document.querySelector("#last-refresh").textContent = `Updated ${formatTimestamp(new Date(), false)}`;
  } catch (_error) {
    document.querySelector("#last-refresh").textContent = "Event service unavailable";
  } finally {
    refreshButton.disabled = false;
  }
}

cameraFeed.addEventListener("error", () => {
  cameraFrame.classList.remove("has-feed");
  cameraPlaceholder.querySelector("strong").textContent = "Camera stream interrupted";
  setState(streamState, "offline", "Offline");
  setPillState(cameraStatus, "offline", "Feed offline");
});

refreshButton.addEventListener("click", refreshEvents);
updateClock();
refreshHealth();
refreshCameraStatus();
refreshEvents();
setInterval(updateClock, 1000);
setInterval(refreshHealth, 5000);
setInterval(refreshCameraStatus, 5000);
setInterval(refreshEvents, 5000);
