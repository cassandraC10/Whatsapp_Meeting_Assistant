const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("captureBridge", {
  openCapture: () => ipcRenderer.send("capture-click"),

  login: (payload) =>
    ipcRenderer.send("capture-login", payload),

  openSignup: () =>
    ipcRenderer.send("capture-signup"),

  startRecording: (payload) =>
    ipcRenderer.send("capture-start", payload),

  pauseResume: () =>
    ipcRenderer.send("capture-pause-resume"),

  finishRecording: () =>
    ipcRenderer.send("capture-finish"),

  cancelCapture: () =>
    ipcRenderer.send("capture-cancel"),

  onState: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("capture-state", handler);

    return () => {
      ipcRenderer.removeListener("capture-state", handler);
    };
  },

  onTick: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("recording-tick", handler);

    return () => {
      ipcRenderer.removeListener("recording-tick", handler);
    };
  },
});
