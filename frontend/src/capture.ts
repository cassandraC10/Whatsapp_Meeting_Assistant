export interface BrowserCaptureSession {
  pause(): void;
  resume(): void;
  stop(): Promise<BrowserCaptureResult>;
  abort(): void;
}

export interface BrowserCaptureResult {
  mic: Blob;
  system: Blob;
  durationSeconds: number;
}

// The capture session intentionally lives outside the React component tree.
// A browser recording must survive a normal SPA/App remount while the media
// tracks are still active. React refs are tied to one component instance and
// can therefore make an otherwise-live MediaRecorder appear to disappear.
let activeBrowserCapture: BrowserCaptureSession | null = null;

export function getActiveBrowserCapture(): BrowserCaptureSession | null {
  return activeBrowserCapture;
}

export function clearActiveBrowserCapture(
  session?: BrowserCaptureSession | null,
): void {
  if (!session || activeBrowserCapture === session) {
    activeBrowserCapture = null;
  }
}

export function abortActiveBrowserCapture(): void {
  const session = activeBrowserCapture;
  if (!session) return;
  activeBrowserCapture = null;
  session.abort();
}

function chooseMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];

  for (const candidate of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(candidate)) {
      return candidate;
    }
  }

  return "";
}

function createRecorder(
  stream: MediaStream,
  mimeType: string,
): { recorder: MediaRecorder; chunks: Blob[] } {
  const chunks: Blob[] = [];
  const recorder = mimeType
    ? new MediaRecorder(stream, { mimeType })
    : new MediaRecorder(stream);

  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size > 0) {
      chunks.push(event.data);
    }
  });

  return { recorder, chunks };
}

function waitForStop(recorder: MediaRecorder): Promise<void> {
  if (recorder.state === "inactive") {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const handleStop = () => {
      cleanup();
      resolve();
    };
    const handleError = () => {
      cleanup();
      reject(new Error("Audio recording failed."));
    };
    const cleanup = () => {
      recorder.removeEventListener("stop", handleStop);
      recorder.removeEventListener("error", handleError);
    };

    recorder.addEventListener("stop", handleStop, { once: true });
    recorder.addEventListener("error", handleError, { once: true });

    try {
      if (recorder.state === "paused") {
        recorder.resume();
      }

      if (recorder.state === "inactive") {
        cleanup();
        resolve();
        return;
      }

      recorder.stop();
    } catch (error) {
      if (recorder.state === "inactive") {
        cleanup();
        resolve();
        return;
      }

      cleanup();
      reject(
        error instanceof Error
          ? error
          : new Error("Audio recording could not be stopped."),
      );
    }
  });
}

function stopTracks(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop());
}

export async function startBrowserCapture(): Promise<BrowserCaptureSession> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("This browser does not support microphone capture.");
  }

  if (!navigator.mediaDevices.getDisplayMedia) {
    throw new Error("This browser does not support system-audio capture. Use a current desktop Chrome or Edge browser.");
  }

  if (typeof MediaRecorder === "undefined") {
    throw new Error("This browser does not support audio recording.");
  }

  const mimeType = chooseMimeType();
  if (!mimeType) {
    throw new Error("This browser does not provide a supported WebM/Opus or Ogg/Opus recorder.");
  }

  let micStream: MediaStream | null = null;
  let displayStream: MediaStream | null = null;

  try {
    const [mic, display] = await Promise.all([
      navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      }),
      navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      }),
    ]);

    micStream = mic;
    displayStream = display;

    const displayAudioTracks = display.getAudioTracks();
    if (displayAudioTracks.length === 0) {
      stopTracks(micStream);
      stopTracks(displayStream);
      throw new Error("No system audio was shared. In the share dialog, choose a tab/window/screen with audio enabled and try again.");
    }

    const systemStream = new MediaStream(displayAudioTracks);
    const micRecording = createRecorder(micStream, mimeType);
    const systemRecording = createRecorder(systemStream, mimeType);

    const startedAt = performance.now();
    let stopped = false;
    let stopPromise: Promise<BrowserCaptureResult> | null = null;

    micRecording.recorder.start(1000);
    systemRecording.recorder.start(1000);

    const cleanup = () => {
      stopTracks(micStream);
      stopTracks(displayStream);
      stopTracks(systemStream);
      micStream = null;
      displayStream = null;
    };

    const session: BrowserCaptureSession = {
      pause() {
        if (stopped) return;
        if (micRecording.recorder.state === "recording") micRecording.recorder.pause();
        if (systemRecording.recorder.state === "recording") systemRecording.recorder.pause();
      },

      resume() {
        if (stopped) return;
        if (micRecording.recorder.state === "paused") micRecording.recorder.resume();
        if (systemRecording.recorder.state === "paused") systemRecording.recorder.resume();
      },

      stop() {
        if (stopPromise) {
          return stopPromise;
        }

        stopped = true;
        stopPromise = (async () => {
          const durationSeconds = Math.max(0, (performance.now() - startedAt) / 1000);

          await Promise.all([
            waitForStop(micRecording.recorder),
            waitForStop(systemRecording.recorder),
          ]);

          cleanup();

          const micBlob = new Blob(micRecording.chunks, { type: micRecording.recorder.mimeType || mimeType });
          const systemBlob = new Blob(systemRecording.chunks, { type: systemRecording.recorder.mimeType || mimeType });

          if (micBlob.size === 0 || systemBlob.size === 0) {
            throw new Error("The browser did not produce usable audio. Please try the capture again.");
          }

          return {
            mic: micBlob,
            system: systemBlob,
            durationSeconds,
          };
        })();

        return stopPromise;
      },

      abort() {
        if (stopped) return;
        stopped = true;
        try {
          if (micRecording.recorder.state !== "inactive") micRecording.recorder.stop();
        } catch {
          // Best-effort cleanup.
        }
        try {
          if (systemRecording.recorder.state !== "inactive") systemRecording.recorder.stop();
        } catch {
          // Best-effort cleanup.
        }
        cleanup();
        clearActiveBrowserCapture(session);
      },
    };

    activeBrowserCapture = session;
    return session;
  } catch (error) {
    if (activeBrowserCapture) {
      activeBrowserCapture = null;
    }
    stopTracks(micStream);
    stopTracks(displayStream);
    throw error instanceof Error
      ? error
      : new Error("Could not start browser audio capture.");
  }
}
