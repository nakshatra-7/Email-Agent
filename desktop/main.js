const { app, BrowserWindow, Tray, Menu, Notification, nativeImage } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

const API_PORT = process.env.API_PORT || 8001;
const API_BASE = `http://127.0.0.1:${API_PORT}/api`;
const POLL_MS = 30000;

let tray = null;
let mainWindow = null;
let backendProc = null;
let agentProc = null;
let seenEventIds = new Set();

function startBackend() {
  if (backendProc) return;
  const cwd = path.join(__dirname, "..", "api");
  const uvicornPath = path.join(cwd, ".venv", "bin", "uvicorn");
  backendProc = spawn(uvicornPath, ["app.main:app", "--host", "127.0.0.1", "--port", String(API_PORT)], {
    cwd,
    env: { ...process.env },
    stdio: "inherit",
  });
  backendProc.on("exit", (code) => {
    backendProc = null;
    console.log(`[backend] exited ${code}`);
  });
}

function startAgent() {
  if (agentProc) return;
  const cwd = path.join(__dirname, "..", "api");
  const pyPath = path.join(cwd, ".venv", "bin", "python");
  agentProc = spawn(pyPath, ["-m", "app.services.agent_runner"], {
    cwd,
    env: { ...process.env },
    stdio: "inherit",
  });
  agentProc.on("exit", (code) => {
    agentProc = null;
    console.log(`[agent] exited ${code}`);
  });
}

function stopAgent() {
  if (agentProc) {
    agentProc.kill();
    agentProc = null;
  }
}

function stopBackend() {
  if (backendProc) {
    backendProc.kill();
    backendProc = null;
  }
}

async function syncOnce() {
  try {
    await fetch(`${API_BASE}/agent/sync_once`, { method: "POST" });
  } catch (err) {
    console.error("sync_once failed", err);
  }
}

function showNotification(title, body) {
  new Notification({ title, body }).show();
}

async function pollEvents() {
  try {
    const res = await fetch(`${API_BASE}/agent/events?limit=10`);
    const data = await res.json();
    for (const evt of data) {
      if (seenEventIds.has(evt.id)) continue;
      seenEventIds.add(evt.id);
      const actions = evt.intent_actions || [];
      const urgency = evt.urgency || "unknown";
      const summary = evt.summary || evt.subject;
      // Notify on high/critical or explicit NOTIFY_USER, and also on any new email arrival.
      showNotification(`New email${urgency ? " (" + urgency + ")" : ""}`, summary);
      if (actions.includes("NOTIFY_USER") || urgency === "high" || urgency === "critical") {
        showNotification(`Urgency: ${urgency}`, summary);
      }
      if (evt.contains_meeting && evt.meeting_details) {
        const md = evt.meeting_details;
        showNotification(
          `Meeting: ${md.title || "Untitled"}`,
          `${md.date || ""} ${md.start_time || ""} ${md.timezone || ""}`.trim()
        );
      }
    }
  } catch (err) {
    console.error("pollEvents failed", err);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 360,
    height: 480,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: true,
      contextIsolation: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, "index.html"));
}

function createTray() {
  const iconCandidate = nativeImage.createFromPath(path.join(__dirname, "icon.png"));
  let icon = iconCandidate;
  if (!icon || icon.isEmpty()) {
    icon = nativeImage.createFromDataURL(
      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIW2NkYGAAAAAEAAGjCh0YAAAAAElFTkSuQmCC"
    );
  }
  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    { label: "Open Dashboard", click: () => mainWindow?.show() },
    { label: "Sync Now", click: () => syncOnce() },
    {
      label: "Start Agent",
      click: () => startAgent(),
    },
    {
      label: "Stop Agent",
      click: () => stopAgent(),
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        stopAgent();
        stopBackend();
        app.quit();
      },
    },
  ]);
  tray.setToolTip("Email Agent");
  tray.setContextMenu(contextMenu);
}

app.whenReady().then(() => {
  startBackend();
  startAgent();
  createWindow();
  createTray();
  setInterval(pollEvents, POLL_MS);
});

app.on("before-quit", () => {
  stopAgent();
  stopBackend();
});

app.on("window-all-closed", (e) => {
  e.preventDefault(); // keep app running in tray
});
