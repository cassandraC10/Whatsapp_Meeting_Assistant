const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("captureBridge", {
  openCapture: () => ipcRenderer.send("capture-click"),
  login: (payload) => ipcRenderer.send("capture-login", payload),
  openSignup: () => ipcRenderer.send("capture-signup"),
  switchAccount: () => ipcRenderer.send("capture-switch-account"),
  startRecording: (payload) => ipcRenderer.send("capture-start", payload),
  pauseResume: () => ipcRenderer.send("capture-pause-resume"),
  finishRecording: () => ipcRenderer.send("capture-finish"),
  cancelCapture: () => ipcRenderer.send("capture-cancel"),
  onState: (callback) => {
    ipcRenderer.on("capture-state", (_event, payload) => callback(payload));
  },
  onTick: (callback) => {
    ipcRenderer.on("recording-tick", (_event, payload) => callback(payload));
  },
});
