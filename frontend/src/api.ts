const API_BASE_URL = "http://127.0.0.1:8000";

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

export async function getCalls(): Promise<Call[]> {
  const response = await fetch(`${API_BASE_URL}/calls`);

  if (!response.ok) {
    throw new Error("Could not load conversations.");
  }

  return response.json();
}

export async function createCall(title: string): Promise<Call> {
  const response = await fetch(`${API_BASE_URL}/calls`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: title.trim() || null,
    }),
  });

  if (!response.ok) {
    throw new Error("Could not create the call.");
  }

  return response.json();
}