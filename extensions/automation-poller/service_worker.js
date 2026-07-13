const DEFAULT_BASE_URL = "https://gyrbuges.duckdns.org";
const POLL_ALARM = "automation-poll";

let isPolling = false;

function randomWorkerId() {
  return `automation-poller-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeBaseUrl(value) {
  return String(value || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

async function getConfig() {
  const stored = await chrome.storage.local.get({
    baseUrl: DEFAULT_BASE_URL,
    secret: "",
    workerId: "",
    enabled: false,
    lastStatus: "idle",
    lastCommandId: "",
    lastUpdatedAt: "",
  });
  if (!stored.workerId) {
    stored.workerId = randomWorkerId();
    await chrome.storage.local.set({ workerId: stored.workerId });
  }
  stored.baseUrl = normalizeBaseUrl(stored.baseUrl);
  return stored;
}

async function setStatus(status, extra = {}) {
  await chrome.storage.local.set({
    lastStatus: status,
    lastUpdatedAt: new Date().toISOString(),
    ...extra,
  });
  chrome.action.setBadgeText({ text: status === "error" ? "!" : "" });
}

async function apiFetch(config, path, options = {}) {
  const separator = path.includes("?") ? "&" : "?";
  const url = `${config.baseUrl}${path}${separator}secret=${encodeURIComponent(config.secret)}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  }
  return body;
}

async function runCommand(command) {
  if (command.action === "echo") {
    return {
      text: String(command.payload?.text || ""),
      echoed_at: new Date().toISOString(),
      worker: "chrome-extension",
    };
  }
  throw new Error(`unsupported automation action: ${command.action}`);
}

async function reportResult(config, command, ok, value) {
  const body = ok
    ? { id: command.id, ok: true, result: value }
    : { id: command.id, ok: false, error: String(value?.message || value || "failed") };
  await apiFetch(config, "/api/automation/result", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

async function pollOnce(force = false) {
  if (isPolling) {
    return { ok: true, skipped: "already polling" };
  }
  const config = await getConfig();
  if (!force && !config.enabled) {
    return { ok: true, skipped: "disabled" };
  }
  if (!config.secret) {
    await setStatus("needs-secret");
    return { ok: false, error: "secret is required" };
  }

  isPolling = true;
  try {
    await setStatus("polling");
    const payload = await apiFetch(
      config,
      `/api/automation/poll?worker_id=${encodeURIComponent(config.workerId)}&wait_seconds=20`,
    );
    if (!payload.command) {
      await setStatus("idle");
      return { ok: true, command: null };
    }

    const command = payload.command;
    await setStatus("running", { lastCommandId: String(command.id) });
    try {
      const result = await runCommand(command);
      await reportResult(config, command, true, result);
      await setStatus("done", { lastCommandId: String(command.id) });
      return { ok: true, commandId: command.id };
    } catch (error) {
      await reportResult(config, command, false, error);
      await setStatus("error", { lastError: String(error.message || error) });
      return { ok: false, error: String(error.message || error) };
    }
  } catch (error) {
    await setStatus("error", { lastError: String(error.message || error) });
    return { ok: false, error: String(error.message || error) };
  } finally {
    isPolling = false;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(POLL_ALARM, { periodInMinutes: 0.5 });
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(POLL_ALARM, { periodInMinutes: 0.5 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === POLL_ALARM) {
    pollOnce(false);
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "get-state") {
    getConfig().then(sendResponse);
    return true;
  }
  if (message?.type === "save-config") {
    const config = {
      baseUrl: normalizeBaseUrl(message.baseUrl),
      secret: String(message.secret || ""),
      enabled: Boolean(message.enabled),
    };
    chrome.storage.local.set(config).then(() => getConfig()).then(sendResponse);
    return true;
  }
  if (message?.type === "poll-now") {
    pollOnce(true).then(sendResponse);
    return true;
  }
  return false;
});
