const baseUrlInput = document.getElementById("baseUrl");
const secretInput = document.getElementById("secret");
const enabledInput = document.getElementById("enabled");
const workerText = document.getElementById("worker");
const statusBox = document.getElementById("status");

function send(message) {
  return chrome.runtime.sendMessage(message);
}

function render(state) {
  baseUrlInput.value = state.baseUrl || "";
  secretInput.value = state.secret || "";
  enabledInput.checked = Boolean(state.enabled);
  workerText.textContent = state.workerId ? `#${state.workerId.slice(-6)}` : "";
  statusBox.textContent = [
    `status: ${state.lastStatus || "idle"}`,
    state.lastCommandId ? `command: ${state.lastCommandId}` : "",
    state.lastError ? `error: ${state.lastError}` : "",
    state.lastUpdatedAt ? `updated: ${state.lastUpdatedAt}` : "",
  ].filter(Boolean).join("\n");
}

async function refresh() {
  render(await send({ type: "get-state" }));
}

document.getElementById("save").addEventListener("click", async () => {
  const state = await send({
    type: "save-config",
    baseUrl: baseUrlInput.value,
    secret: secretInput.value,
    enabled: enabledInput.checked,
  });
  render(state);
});

document.getElementById("poll").addEventListener("click", async () => {
  statusBox.textContent = "polling...";
  const result = await send({ type: "poll-now" });
  await refresh();
  if (!result?.ok) {
    statusBox.textContent += `\n${result?.error || "poll failed"}`;
  }
});

refresh();
