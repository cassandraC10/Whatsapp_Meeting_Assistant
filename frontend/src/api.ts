const API_BASE_URL =
  "http://127.0.0.1:8000";

export type CallStatus =
  | "created"
  | "recording"
  | "paused"
  | "processing"
  | "completed"
  | "failed";

export interface Call {
  id: string;
  title: string;
  created_at: string;
  duration_seconds: number;
  status: CallStatus;
}

export interface ActionItem {
  task: string;
  deadline: string | null;
}

export interface Decision {
  decision: string;
}

export interface CallNotes {
  title: string;
  summary: string;
  key_points: string[];
  decisions: Decision[];
  my_action_items: ActionItem[];
  their_action_items: ActionItem[];
  important_dates: string[];
  follow_up: string | null;
}

export interface NotesResponse {
  call: Call;
  notes: CallNotes;
}

export interface TranscriptResponse {
  call_id: string;
  transcript: string;
}

export interface RecordingStatusResponse {
  call_id: string;
  status: CallStatus;
  is_recording: boolean;
  is_paused: boolean;
  elapsed_seconds: number;
}

export interface FinishRecordingResponse {
  call: Call;

  recording: {
    mic: string;
    system: string;
    mixed: string;
    duration_seconds: number;
  };
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    options
  );

  if (!response.ok) {
    let message =
      "Something went wrong.";

    try {
      const data =
        await response.json();

      if (data.detail) {
        message = data.detail;
      }

    } catch {
      // Keep fallback message.
    }

    throw new Error(message);
  }

  return response.json();
}

export function getCalls():
Promise<Call[]> {
  return request<Call[]>(
    "/calls"
  );
}

export function getCall(
  callId: string
): Promise<Call> {
  return request<Call>(
    `/calls/${callId}`
  );
}

export function createCall(
  title: string
): Promise<Call> {
  return request<Call>(
    "/calls",
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
      },

      body: JSON.stringify({
        title:
          title.trim() || null,
      }),
    }
  );
}

export function startCallRecording(
  callId: string
): Promise<Call> {
  return request<Call>(
    `/calls/${callId}/start`,
    {
      method: "POST",
    }
  );
}

export function pauseCallRecording(
  callId: string
): Promise<Call> {
  return request<Call>(
    `/calls/${callId}/pause`,
    {
      method: "POST",
    }
  );
}

export function resumeCallRecording(
  callId: string
): Promise<Call> {
  return request<Call>(
    `/calls/${callId}/resume`,
    {
      method: "POST",
    }
  );
}

export function getRecordingStatus(
  callId: string
): Promise<RecordingStatusResponse> {
  return request<RecordingStatusResponse>(
    `/calls/${callId}/recording-status`
  );
}

export function finishCallRecording(
  callId: string
): Promise<FinishRecordingResponse> {
  return request<FinishRecordingResponse>(
    `/calls/${callId}/finish`,
    {
      method: "POST",
    }
  );
}

export async function processCall(
  callId: string
): Promise<void> {
  await request<unknown>(
    `/calls/${callId}/process`,
    {
      method: "POST",
    }
  );
}

export function getCallNotes(
  callId: string
): Promise<NotesResponse> {
  return request<NotesResponse>(
    `/calls/${callId}/notes`
  );
}

export function getCallTranscript(
  callId: string
): Promise<TranscriptResponse> {
  return request<TranscriptResponse>(
    `/calls/${callId}/transcript`
  );
}