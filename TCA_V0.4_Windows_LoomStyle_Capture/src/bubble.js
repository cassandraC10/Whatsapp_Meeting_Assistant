const root = document.getElementById("root");

let current = {
  state: "idle",
  title: "",
  consent: false,
  elapsed: 0,
  error: "",
  call: null,
  user: null,
};

function formatTimer(seconds) {
  const total = Math.max(0, Math.round(seconds || 0));
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;

  return [
    String(minutes).padStart(2, "0"),
    String(remaining).padStart(2, "0"),
  ].join(":");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function render() {
  const state = current.state;

  if (state === "idle") {
    root.className = "shell";
    root.innerHTML = `
      <button id="bubble" class="bubble" aria-label="Capture conversation" title="Capture conversation">
        <span class="bubble-mark" aria-hidden="true"></span>
      </button>
      <span class="hint">Capture</span>
    `;

    document.getElementById("bubble").addEventListener("click", () => {
      window.captureBridge.openCapture();
    });

    return;
  }

  root.className = "shell";
  root.innerHTML = `
    <section class="panel" aria-label="Conversation capture">
      <header class="panel-header">
        <div class="brand">
          <span class="brand-dot"></span>
          Conversation Assistant
        </div>
        <button id="close" class="close" aria-label="Close">×</button>
      </header>
      ${renderBody()}
    </section>
  `;

  document.getElementById("close").addEventListener("click", () => {
    if (["recording", "paused", "starting", "finishing", "processing", "logging-in"].includes(current.state)) {
      return;
    }

    window.captureBridge.cancelCapture();
  });

  bindState();
}

function renderBody() {
  if (current.state === "login" || current.state === "logging-in") {
    const busy = current.state === "logging-in";

    return `
      <p class="eyebrow">Private capture</p>
      <h1>Sign in to capture.</h1>
      <p class="copy">
        Your conversations are private to your TCA account.
      </p>

      <label class="title-label" for="email">Email</label>
      <input
        id="email"
        class="title-input"
        type="email"
        placeholder="you@example.com"
        autocomplete="email"
        ${busy ? "disabled" : ""}
      />

      <label class="title-label auth-password-label" for="password">Password</label>
      <input
        id="password"
        class="title-input"
        type="password"
        placeholder="Your password"
        autocomplete="current-password"
        ${busy ? "disabled" : ""}
      />

      <button id="login" class="primary" ${busy ? "disabled" : ""}>
        ${busy ? "Signing in…" : "Sign in"}
      </button>

      <button id="signup" class="secondary auth-signup-button" ${busy ? "disabled" : ""}>
        Create account in TCA
      </button>

      ${current.error ? `<div class="error">${escapeHtml(current.error)}</div>` : ""}
    `;
  }

  if (current.state === "consent") {
    return `
      <p class="eyebrow">Quick capture</p>
      <h1>Ready when you are.</h1>
      <p class="copy">
        TCA will record your microphone and the audio playing through your computer.
      </p>

      <label class="title-label" for="title">
        Title <span class="optional">Optional</span>
      </label>

      <input
        id="title"
        class="title-input"
        value="${escapeHtml(current.title)}"
        placeholder="e.g. Product feedback with Jane"
        maxlength="120"
        autocomplete="off"
      />

      <label class="consent">
        <input id="consent" type="checkbox" ${current.consent ? "checked" : ""} />
        <span class="check"></span>
        <span>I've told everyone on this call that I'm recording.</span>
      </label>

      <button id="start" class="primary" disabled>
        Start recording
      </button>

      ${current.error ? `<div class="error">${escapeHtml(current.error)}</div>` : ""}
    `;
  }

  if (current.state === "starting") {
    return `
      <div class="status-copy">
        <div class="spinner"></div>
        <h1>Starting recording…</h1>
        <p>Getting your conversation capture ready.</p>
      </div>
    `;
  }

  if (current.state === "recording" || current.state === "paused") {
    const paused = current.state === "paused";
    const title = current.call?.title || current.title || "Conversation";

    return `
      <div class="recording-center">
        <div class="recording-orb">
          <span></span>
        </div>

        <div class="${paused ? "live paused" : "live"}">
          ${paused ? "" : '<span class="live-dot"></span>'}
          ${paused ? "Paused" : "Recording"}
        </div>

        <div class="timer">${formatTimer(current.elapsed)}</div>

        <p class="call-title" title="${escapeHtml(title)}">
          ${escapeHtml(title)}
        </p>
      </div>

      <div class="recording-actions">
        <button id="pause" class="secondary">
          ${paused ? "Resume" : "Pause"}
        </button>

        <button id="finish" class="finish">
          Finish call
        </button>
      </div>

      ${current.error ? `<div class="error">${escapeHtml(current.error)}</div>` : ""}
    `;
  }

  if (current.state === "finishing") {
    return `
      <div class="status-copy">
        <div class="spinner"></div>
        <h1>Saving recording…</h1>
        <p>Making sure your conversation is safely stored.</p>
      </div>
    `;
  }

  if (current.state === "processing") {
    return `
      <div class="status-copy">
        <div class="spinner"></div>
        <h1>Preparing your memory…</h1>
        <p>TCA is turning the conversation into a useful recap.</p>
      </div>
    `;
  }

  if (current.state === "complete") {
    return `
      <div class="status-copy">
        <div class="recording-orb">
          <span></span>
        </div>
        <h1>Saved.</h1>
        <p>Your conversation is ready in TCA.</p>
      </div>
    `;
  }

  if (current.state === "error") {
    return `
      <div class="status-copy">
        <h1>Something went wrong.</h1>
        <p>${escapeHtml(current.error || "The recording could not be completed.")}</p>
        <button id="retry" class="primary" style="margin-top:18px;">
          Back to capture
        </button>
      </div>
    `;
  }

  return "";
}

function bindState() {
  if (current.state === "login") {
    const email = document.getElementById("email");
    const password = document.getElementById("password");
    const login = document.getElementById("login");
    const signup = document.getElementById("signup");

    const submit = () => {
      window.captureBridge.login({
        email: email.value,
        password: password.value,
      });
    };

    login.addEventListener("click", submit);
    password.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        submit();
      }
    });

    signup.addEventListener("click", () => {
      window.captureBridge.openSignup();
    });

    setTimeout(() => email.focus(), 0);
    return;
  }

  if (current.state === "consent") {
    const title = document.getElementById("title");
    const consent = document.getElementById("consent");
    const start = document.getElementById("start");

    const updateStart = () => {
      current.title = title.value;
      current.consent = consent.checked;
      start.disabled = !current.consent;
    };

    title.addEventListener("input", updateStart);
    consent.addEventListener("change", updateStart);
    start.addEventListener("click", () => {
      window.captureBridge.startRecording({
        title: current.title,
        consentConfirmed: current.consent,
      });
    });

    setTimeout(() => title.focus(), 0);
    updateStart();
  }

  if (current.state === "recording" || current.state === "paused") {
    document.getElementById("pause").addEventListener("click", () => {
      window.captureBridge.pauseResume();
    });

    document.getElementById("finish").addEventListener("click", () => {
      window.captureBridge.finishRecording();
    });
  }

  if (current.state === "error") {
    document.getElementById("retry").addEventListener("click", () => {
      current = {
        state: "consent",
        title: current.title || "",
        consent: false,
        elapsed: 0,
        error: "",
        call: null,
        user: current.user,
      };
      render();
    });
  }
}

window.captureBridge.onState((payload) => {
  current = {
    ...current,
    ...payload,
    state: payload.state || current.state,
    error: payload.error || "",
  };

  render();
});

window.captureBridge.onTick((payload) => {
  current.elapsed = payload.elapsed_seconds || 0;

  const timer = document.querySelector(".timer");
  if (timer) {
    timer.textContent = formatTimer(current.elapsed);
  }
});

render();
