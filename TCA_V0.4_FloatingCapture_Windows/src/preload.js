const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("captureBridge", {
  openCapture: () => ipcRenderer.send("capture-click"),
});
