document.addEventListener("DOMContentLoaded", () => {
  const capture = document.getElementById("capture");

  if (!capture) return;

  capture.addEventListener("click", () => {
    window.captureBridge.openCapture();
  });
});
