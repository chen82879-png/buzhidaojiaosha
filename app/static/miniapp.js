if (window.Telegram && window.Telegram.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

window.copyText = copyText;

document.addEventListener("click", (event) => {
  const button = event.target.closest(".mini-action-button");
  if (!button) {
    return;
  }
  const form = button.closest("form");
  if (!form || button.type === "submit") {
    return;
  }
  const checked = button.textContent.trim() === "全选";
  form.querySelectorAll(".wait-keyword-checkbox").forEach((input) => {
    input.checked = checked;
  });
});

function formatCountdown(seconds) {
  if (seconds <= 0) {
    return "已到期";
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function updateCountdowns() {
  const now = Math.floor(Date.now() / 1000);
  document.querySelectorAll(".mini-countdown[data-due]").forEach((node) => {
    const due = Number(node.dataset.due || 0);
    const remaining = due - now;
    node.textContent = formatCountdown(remaining);
    node.classList.toggle("late", remaining <= 0);
  });
}

async function refreshTaskPage() {
  const region = document.getElementById("task-live-region");
  if (!region || document.hidden) {
    return;
  }
  try {
    const response = await fetch(`/mini/tasks?_=${Date.now()}`, {
      headers: { "X-Requested-With": "fetch" },
      cache: "no-store",
    });
    if (!response.ok) {
      return;
    }
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    const nextRegion = doc.getElementById("task-live-region");
    const nextSummary = doc.querySelector(".mini-task-summary");
    const currentSummary = document.querySelector(".mini-task-summary");
    if (nextRegion) {
      region.innerHTML = nextRegion.innerHTML;
    }
    if (nextSummary && currentSummary) {
      currentSummary.innerHTML = nextSummary.innerHTML;
    }
    updateCountdowns();
  } catch (_) {
    // Keep the current rendered page if refresh fails.
  }
}

updateCountdowns();
setInterval(updateCountdowns, 1000);
setInterval(refreshTaskPage, 5000);
