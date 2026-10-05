const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  shell,
  screen,
  ipcMain,
  safeStorage,
} = require("electron");
const fs = require("fs");
const path = require("path");

const DEFAULT_TCA_URL = "http://localhost:5173/";
const API_BASE_URL = "http://127.0.0.1:8000";
const AUTH_FILE_NAME = "auth-token.bin";
const PROTOCOL_SCHEME = "tca-capture";

const gotSingleInstanceLock = app.requestSingleInstanceLock();

if (!gotSingleInstanceLock) {
  app.quit();
}

let bubbleWindow = null;
let tray = null;
let isQuitting = false;
let authToken = null;
let pendingCaptureHandoffCode = null;

let captureState = "idle";
let activeCall = null;
let elapsedSeconds = 0;
let timer = null;

function getTcaUrl(capture = false, signup = false) {
  const base = process.env.TCA_URL?.trim() || DEFAULT_TCA_URL;

  try {
    const url = new URL(base);
    if (capture) {
      url.searchParams.set("capture", "1");
    }
    if (signup) {
      url.searchParams.set("signup", "1");
    }
    return url.toString();
  } catch {
    return base;
  }
}

function apiUrl(pathname) {
  return `${API_BASE_URL}${pathname}`;
}

function authFilePath() {
  return path.join(app.getPath("userData"), AUTH_FILE_NAME);
}

function loadStoredToken() {
  try {
    const file = authFilePath();
    if (!fs.existsSync(file)) {
      return null;
    }

    const raw = fs.readFileSync(file);

    if (safeStorage.isEncryptionAvailable()) {
      return safeStorage.decryptString(raw).trim() || null;
    }

    return raw.toString("utf8").trim() || null;
  } catch {
    return null;
  }
}

function saveStoredToken(token) {
  fs.mkdirSync(path.dirname(authFilePath()), { recursive: true });

  if (safeStorage.isEncryptionAvailable()) {
    fs.writeFileSync(
      authFilePath(),
      safeStorage.encryptString(token),
    );
    return;
  }

  fs.writeFileSync(authFilePath(), token, "utf8");
}

function clearStoredToken() {
  try {
    fs.rmSync(authFilePath(), { force: true });
  } catch {
    // Ignore cleanup failures.
  }
}

function setAuthToken(token) {
  authToken = token;
  saveStoredToken(token);
}

function clearAuthToken() {
  authToken = null;
  clearStoredToken();
}

function isAuthenticated() {
  return Boolean(authToken);
}

async function apiRequest(pathname, options = {}) {
  const headers = {
    Accept: "application/json",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };

  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(apiUrl(pathname), {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;

    try {
      const data = await response.json();
      if (data?.detail) {
        message = String(data.detail);
      }
    } catch {
      // Keep fallback.
    }

    if (response.status === 401) {
      clearAuthToken();

      if (captureState !== "recording" && captureState !== "paused") {
        setCaptureState("login", {
          error: "Your capture session expired. Please sign in again.",
        });
      }
    }

    throw new Error(message);
  }

  return response.json();
}

function setCaptureState(state, data = {}) {
  captureState = state;

  if (!bubbleWindow || bubbleWindow.isDestroyed()) {
    return;
  }

  bubbleWindow.webContents.send("capture-state", {
    state,
    ...data,
  });
}

function stopTimer() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function startTimer() {
  stopTimer();

  timer = setInterval(() => {
    elapsedSeconds += 1;

    if (bubbleWindow && !bubbleWindow.isDestroyed()) {
      bubbleWindow.webContents.send("recording-tick", {
        elapsed_seconds: elapsedSeconds,
      });
    }
  }, 1000);
}

function formatPanelSize() {
  if (captureState === "idle") {
    return { width: 72, height: 72 };
  }

  return { width: 360, height: 420 };
}

function positionBubble() {
  if (!bubbleWindow || bubbleWindow.isDestroyed()) {
    return;
  }

  const workArea = screen.getPrimaryDisplay().workArea;
  const { width, height } = formatPanelSize();
  const margin = 24;

  bubbleWindow.setSize(width, height);

  bubbleWindow.setPosition(
    Math.round(workArea.x + workArea.width - width - margin),
    Math.round(workArea.y + workArea.height - height - margin),
  );
}

function createBubble() {
  if (bubbleWindow && !bubbleWindow.isDestroyed()) {
    return;
  }

  bubbleWindow = new BrowserWindow({
    width: 72,
    height: 72,
    frame: false,
    transparent: true,
    resizable: false,
    movable: true,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    hasShadow: false,
    show: false,
    backgroundColor: "#00000000",
    webPreferences: {
      contextIsolation: true,
      sandbox: false,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  bubbleWindow.setAlwaysOnTop(true, "floating");
  bubbleWindow.loadFile(path.join(__dirname, "bubble.html"));

  bubbleWindow.once("ready-to-show", async () => {
    positionBubble();
    bubbleWindow.showInactive();

    if (pendingCaptureHandoffCode) {
      const code = pendingCaptureHandoffCode;
      pendingCaptureHandoffCode = null;
      await exchangeCaptureHandoff(code);
    }
  });

  bubbleWindow.on("closed", () => {
    stopTimer();
    bubbleWindow = null;
  });
}

function resizeAndPosition() {
  positionBubble();

  if (bubbleWindow && !bubbleWindow.isDestroyed()) {
    bubbleWindow.show();
    bubbleWindow.focus();
  }
}

async function openTca(capture = false) {
  await shell.openExternal(getTcaUrl(capture));
}

async function openSignup() {
  await shell.openExternal(getTcaUrl(false, true));
}

function createTray() {
  if (tray) {
    return;
  }

  const icon = nativeImage.createFromPath(
    path.join(__dirname, "icon-512.png"),
  );

  tray = new Tray(icon);
  tray.setToolTip("Conversation Assistant Capture");

  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: "Capture conversation",
        click: () => {
          void expandCapture();
        },
      },
      {
        label: "Open TCA",
        click: () => void openTca(false),
      },
      {
        label: "Create account",
        click: () => void openSignup(),
      },
      { type: "separator" },
      {
        label: "Sign out of Capture",
        click: () => {
          if (captureState === "recording" || captureState === "paused") {
            return;
          }

          clearAuthToken();
          resetToIdle();
        },
      },
      {
        label: "Move Capture to corner",
        click: positionBubble,
      },
      { type: "separator" },
      {
        label: "Quit Capture",
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]),
  );

  tray.on("click", () => {
    void expandCapture();
  });
}

function resetToIdle() {
  stopTimer();
  captureState = "idle";
  activeCall = null;
  elapsedSeconds = 0;

  if (bubbleWindow && !bubbleWindow.isDestroyed()) {
    bubbleWindow.webContents.send("capture-state", {
      state: "idle",
    });
    resizeAndPosition();
  }
}

function parseCaptureProtocolUrl(value) {
  if (!value || !value.startsWith(`${PROTOCOL_SCHEME}://`)) {
    return null;
  }

  try {
    const url = new URL(value);
    if (url.hostname !== "auth") {
      return null;
    }

    const code = url.searchParams.get("code")?.trim();
    return code || null;
  } catch {
    return null;
  }
}

function extractProtocolUrl(argv) {
  return argv.find((argument) =>
    typeof argument === "string"
    && argument.startsWith(`${PROTOCOL_SCHEME}://`),
  ) || null;
}

async function exchangeCaptureHandoff(code) {
  try {
    const response = await fetch(apiUrl("/auth/capture-handoff/exchange"), {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      let message = "This TCA connection has expired. Please connect Capture again.";
      try {
        const data = await response.json();
        if (data?.detail) {
          message = String(data.detail);
        }
      } catch {
        // Keep fallback.
      }

      setCaptureState("login", { error: message });
      resizeAndPosition();
      return;
    }

    const result = await response.json();
    setAuthToken(result.access_token);

    if (!result.user?.onboarding_completed) {
      setCaptureState("setup", {
        user: result.user,
        error: "Finish your TCA identity setup before using Capture.",
      });
    } else {
      setCaptureState("consent", {
        user: result.user,
        error: "",
      });
    }

    resizeAndPosition();
  } catch (error) {
    setCaptureState("login", {
      error:
        error instanceof Error
          ? error.message
          : "Could not connect this Capture companion.",
    });
    resizeAndPosition();
  }
}

async function handleCaptureProtocolUrl(value) {
  const code = parseCaptureProtocolUrl(value);
  if (!code) {
    return;
  }

  if (!bubbleWindow || bubbleWindow.isDestroyed()) {
    pendingCaptureHandoffCode = code;
    createBubble();
    return;
  }

  await exchangeCaptureHandoff(code);
}

async function expandCapture() {
  if (!bubbleWindow || bubbleWindow.isDestroyed()) {
    createBubble();
    return;
  }

  if (captureState === "idle") {
    if (isAuthenticated()) {
      try {
        const result = await apiRequest("/auth/me");

        if (!result.onboarding_completed) {
          captureState = "setup";
          resizeAndPosition();
          bubbleWindow.webContents.send("capture-state", {
            state: captureState,
            user: result,
            error: "Finish your TCA identity setup before using Capture.",
          });
          return;
        }

        captureState = "consent";
        resizeAndPosition();
        bubbleWindow.webContents.send("capture-state", {
          state: captureState,
          user: result,
        });
      } catch {
        captureState = "login";
        resizeAndPosition();
        bubbleWindow.webContents.send("capture-state", {
          state: captureState,
        });
      }
    } else {
      captureState = "login";
      resizeAndPosition();
      bubbleWindow.webContents.send("capture-state", {
        state: captureState,
      });
    }
  } else {
    bubbleWindow.show();
    bubbleWindow.focus();
  }
}

async function loginFromCompanion({ email, password }) {
  try {
    setCaptureState("logging-in");

    const result = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: String(email || "").trim(),
        password: String(password || ""),
      }),
    });

    setAuthToken(result.access_token);

    if (!result.user?.onboarding_completed) {
      setCaptureState("setup", {
        user: result.user,
        error: "Finish your TCA identity setup before using Capture.",
      });
      return;
    }

    setCaptureState("consent", {
      user: result.user,
      error: "",
    });
  } catch (error) {
    setCaptureState("login", {
      error:
        error instanceof Error
          ? error.message
          : "Could not sign in.",
    });
  }
}

async function startRecording({ title, consentConfirmed }) {
  if (captureState !== "consent" || !consentConfirmed) {
    return;
  }

  if (!isAuthenticated()) {
    setCaptureState("login", {
      error: "Please sign in before starting a capture.",
    });
    return;
  }

  try {
    setCaptureState("starting");

    const call = await apiRequest("/calls", {
      method: "POST",
      body: JSON.stringify({
        title: String(title || "").trim() || null,
      }),
    });

    activeCall = call;

    const startedCall = await apiRequest(
      `/calls/${encodeURIComponent(call.id)}/start`,
      { method: "POST" },
    );

    activeCall = startedCall;
    elapsedSeconds = 0;

    setCaptureState("recording", {
      call: startedCall,
      elapsed_seconds: 0,
    });

    startTimer();
  } catch (error) {
    activeCall = null;

    setCaptureState("consent", {
      error:
        error instanceof Error
          ? error.message
          : "Could not start recording.",
    });
  }
}

async function finishRecording() {
  if (
    !activeCall
    || (captureState !== "recording" && captureState !== "paused")
  ) {
    return;
  }

  const callId = activeCall.id;

  try {
    setCaptureState("finishing", {
      elapsed_seconds: elapsedSeconds,
    });

    stopTimer();

    const result = await apiRequest(
      `/calls/${encodeURIComponent(callId)}/finish`,
      { method: "POST" },
    );

    activeCall = result.call;
    elapsedSeconds = result.recording.duration_seconds;

    setCaptureState("processing", {
      call: result.call,
      elapsed_seconds: elapsedSeconds,
    });

    await apiRequest(
      `/calls/${encodeURIComponent(callId)}/process`,
      { method: "POST" },
    );

    const completedCall = await apiRequest(
      `/calls/${encodeURIComponent(callId)}`,
    );

    setCaptureState("complete", {
      call: completedCall,
    });

    setTimeout(() => {
      resetToIdle();
      void openTca(false);
    }, 900);
  } catch (error) {
    stopTimer();

    setCaptureState("error", {
      error:
        error instanceof Error
          ? error.message
          : "Could not finish this recording.",
      call: activeCall,
    });
  }
}

async function pauseResumeRecording() {
  if (!activeCall) {
    return;
  }

  const callId = activeCall.id;

  try {
    if (captureState === "recording") {
      const pausedCall = await apiRequest(
        `/calls/${encodeURIComponent(callId)}/pause`,
        { method: "POST" },
      );

      stopTimer();
      activeCall = pausedCall;

      setCaptureState("paused", {
        call: pausedCall,
        elapsed_seconds: elapsedSeconds,
      });

      return;
    }

    if (captureState === "paused") {
      const resumedCall = await apiRequest(
        `/calls/${encodeURIComponent(callId)}/resume`,
        { method: "POST" },
      );

      activeCall = resumedCall;
      setCaptureState("recording", {
        call: resumedCall,
        elapsed_seconds: elapsedSeconds,
      });

      startTimer();
    }
  } catch (error) {
    setCaptureState(captureState, {
      call: activeCall,
      elapsed_seconds: elapsedSeconds,
      error:
        error instanceof Error
          ? error.message
          : "Could not change recording state.",
    });
  }
}

async function cancelCapture() {
  if (
    captureState === "recording"
    || captureState === "paused"
    || captureState === "starting"
    || captureState === "finishing"
    || captureState === "processing"
    || captureState === "logging-in"
  ) {
    return;
  }

  resetToIdle();
}

ipcMain.on("capture-click", () => {
  void expandCapture();
});

ipcMain.on("capture-login", (_event, payload) => {
  void loginFromCompanion(payload || {});
});

ipcMain.on("capture-signup", () => {
  void openSignup();
});

ipcMain.on("capture-open-tca", () => {
  void openTca(true);
});

ipcMain.on("capture-switch-account", () => {
  if (
    captureState === "recording"
    || captureState === "paused"
    || captureState === "starting"
    || captureState === "finishing"
    || captureState === "processing"
  ) {
    return;
  }

  clearAuthToken();
  captureState = "login";
  activeCall = null;
  elapsedSeconds = 0;

  if (bubbleWindow && !bubbleWindow.isDestroyed()) {
    resizeAndPosition();
    bubbleWindow.webContents.send("capture-state", {
      state: "login",
      error: "",
    });
  }
});

ipcMain.on("capture-start", (_event, payload) => {
  void startRecording(payload || {});
});

ipcMain.on("capture-pause-resume", () => {
  void pauseResumeRecording();
});

ipcMain.on("capture-finish", () => {
  void finishRecording();
});

ipcMain.on("capture-cancel", () => {
  void cancelCapture();
});

function registerCaptureProtocol() {
  if (process.defaultApp) {
    const entry = process.argv[1]
      ? path.resolve(process.argv[1])
      : path.resolve(__dirname, "..", "package.json");

    app.setAsDefaultProtocolClient(
      PROTOCOL_SCHEME,
      process.execPath,
      [entry],
    );
  } else {
    app.setAsDefaultProtocolClient(PROTOCOL_SCHEME);
  }
}

if (gotSingleInstanceLock) {
  app.on("second-instance", (_event, commandLine) => {
    const protocolUrl = extractProtocolUrl(commandLine);

    if (protocolUrl) {
      void handleCaptureProtocolUrl(protocolUrl);
    }

    if (bubbleWindow && !bubbleWindow.isDestroyed()) {
      bubbleWindow.show();
      bubbleWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    app.setAppUserModelId("com.tca.floatingcapture");
    registerCaptureProtocol();

    authToken = loadStoredToken();

    createBubble();
    createTray();

    screen.on("display-metrics-changed", positionBubble);
    screen.on("display-added", positionBubble);
    screen.on("display-removed", positionBubble);

    app.on("activate", () => {
      createBubble();
    });

    const initialProtocolUrl = extractProtocolUrl(process.argv);
    if (initialProtocolUrl) {
      await handleCaptureProtocolUrl(initialProtocolUrl);
    }
  });
}

app.on("open-url", (event, url) => {
  event.preventDefault();
  void handleCaptureProtocolUrl(url);
});

app.on("before-quit", () => {
  isQuitting = true;
  stopTimer();
});

app.on("window-all-closed", (event) => {
  if (!isQuitting) {
    event.preventDefault();
  }
});
