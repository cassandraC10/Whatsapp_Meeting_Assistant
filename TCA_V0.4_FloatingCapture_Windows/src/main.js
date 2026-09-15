const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  shell,
  screen,
  ipcMain,
} = require("electron");
const path = require("path");

const DEFAULT_TCA_URL = "http://localhost:5173/";
let bubbleWindow = null;
let tray = null;
let isQuitting = false;

function getTcaUrl(capture = true) {
  const base = process.env.TCA_URL?.trim() || DEFAULT_TCA_URL;
  try {
    const url = new URL(base);
    if (capture) url.searchParams.set("capture", "1");
    return url.toString();
  } catch {
    return `${DEFAULT_TCA_URL}?capture=1`;
  }
}

function positionBubble() {
  if (!bubbleWindow || bubbleWindow.isDestroyed()) return;
  const workArea = screen.getPrimaryDisplay().workArea;
  const [width, height] = bubbleWindow.getSize();
  const margin = 24;
  bubbleWindow.setPosition(
    Math.round(workArea.x + workArea.width - width - margin),
    Math.round(workArea.y + workArea.height - height - margin)
  );
}

function createBubble() {
  if (bubbleWindow && !bubbleWindow.isDestroyed()) return;

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

  bubbleWindow.once("ready-to-show", () => {
    positionBubble();
    bubbleWindow.showInactive();
  });

  bubbleWindow.on("closed", () => {
    bubbleWindow = null;
  });
}

async function openCapture() {
  await shell.openExternal(getTcaUrl(true));
}

async function openTca() {
  await shell.openExternal(getTcaUrl(false));
}

function createTray() {
  if (tray) return;

  const icon = nativeImage.createFromPath(path.join(__dirname, "tray.png"));
  tray = new Tray(icon);
  tray.setToolTip("Conversation Assistant Capture");

  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Capture conversation", click: () => void openCapture() },
    { label: "Open TCA", click: () => void openTca() },
    { type: "separator" },
    { label: "Move Capture to corner", click: positionBubble },
    { type: "separator" },
    {
      label: "Quit Capture",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]));

  tray.on("click", () => void openCapture());
}

ipcMain.on("capture-click", () => void openCapture());

app.whenReady().then(() => {
  app.setAppUserModelId("com.tca.floatingcapture");
  createBubble();
  createTray();

  screen.on("display-metrics-changed", positionBubble);
  screen.on("display-added", positionBubble);
  screen.on("display-removed", positionBubble);

  app.on("activate", () => createBubble());
});

app.on("before-quit", () => {
  isQuitting = true;
});

app.on("window-all-closed", (event) => {
  if (!isQuitting) event.preventDefault();
});
