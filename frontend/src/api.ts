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
  failure_reason: string | null;
}


export interface ActionItem {
  task: string;
  deadline: string | null;
}


export interface Decision {
  decision: string;
}


export interface Participant {
  role: "me" | "them";
  name: string | null;
  source: string | null;
}


export interface CallNotes {
  title: string;
  summary: string;
  participants: Participant[];
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
  failure_reason: string | null;
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




export type TaskOwner =
  | "me"
  | "them";


export interface Task {
  id: string;
  call_id: string;
  owner: TaskOwner;
  task: string;
  deadline: string | null;
  completed: boolean;
}


export interface TasksResponse {
  call_id: string;
  tasks: Task[];
}


export interface UpdateTaskRequest {
  task?: string;
  deadline?: string | null;
  completed?: boolean;
}


export interface DeleteTaskResponse {
  status: "deleted";
  call_id: string;
  task_id: string;
}


export interface DeleteCallResponse {
  status: "deleted";
  call_id: string;
}


export interface SearchResult {
  call: Call;
  snippet: string;
  matched_in: string[];
}


export interface SearchCallsResponse {
  query: string;
  count: number;
  results: SearchResult[];
}


export interface AskSource {
  call_id: string;
  title: string;
  created_at: string;
  snippet: string | null;
}


export interface AskResponse {
  answer: string;
  sources: AskSource[];
  found_answer: boolean;
}


export interface FollowUpResponse {
  call_id: string;
  recipient_name: string | null;
  message: string;
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
        message =
          data.detail;
      }

    } catch {
      // Keep fallback message.
    }

    throw new Error(
      message
    );
  }

  return response.json();
}


export function getCalls():
Promise<Call[]> {
  return request<Call[]>(
    "/calls"
  );
}


export function searchCalls(
  query: string
): Promise<SearchCallsResponse> {
  const cleanQuery =
    query.trim();

  if (!cleanQuery) {
    return Promise.resolve({
      query: "",
      count: 0,
      results: [],
    });
  }

  return request<SearchCallsResponse>(
    `/calls/search?q=${
      encodeURIComponent(
        cleanQuery
      )
    }`
  );
}


export function askTca(
  question: string,
  callId?: string
): Promise<AskResponse> {
  const cleanQuestion =
    question.trim();

  const body: {
    question: string;
    call_id?: string;
  } = {
    question:
      cleanQuestion,
  };

  if (callId) {
    body.call_id = callId;
  }

  return request<AskResponse>(
    "/ask",
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
        "Accept":
          "application/json",
      },

      body:
        JSON.stringify(body),
    }
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
          title.trim()
          || null,
      }),
    }
  );
}


export function updateCallTitle(
  callId: string,
  title: string
): Promise<Call> {
  return request<Call>(
    `/calls/${callId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type":
          "application/json",
        "Accept":
          "application/json",
      },
      body: JSON.stringify({
        title: title.trim(),
      }),
    }
  );
}


export function deleteCall(
  callId: string
): Promise<DeleteCallResponse> {
  return request<DeleteCallResponse>(
    `/calls/${callId}`,
    {
      method: "DELETE",
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


export function generateCallFollowUp(
  callId: string
): Promise<FollowUpResponse> {
  return request<FollowUpResponse>(
    `/calls/${callId}/follow-up`,
    {
      method: "POST",
      headers: {
        "Accept":
          "application/json",
      },
    }
  );
}

export function getCallTasks(
  callId: string
): Promise<TasksResponse> {
  return request<TasksResponse>(
    `/calls/${callId}/tasks`
  );
}


export function updateCallTask(
  callId: string,
  taskId: string,
  changes: UpdateTaskRequest
): Promise<Task> {
  return request<Task>(
    `/calls/${callId}/tasks/${taskId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify(changes),
    }
  );
}


export function deleteCallTask(
  callId: string,
  taskId: string
): Promise<DeleteTaskResponse> {
  return request<DeleteTaskResponse>(
    `/calls/${callId}/tasks/${taskId}`,
    {
      method: "DELETE",
    }
  );
}


export interface Person {
  id: string;
  name: string;
  conversation_count: number;
}

export interface PersonTask {
  id: string;
  call_id: string;
  task: string;
  deadline: string | null;
  completed: boolean;
}

export interface PersonDetail {
  id: string;
  name: string;
  conversation_count: number;
  open_next_steps: PersonTask[];
  recent_decisions: string[];
  conversations: Call[];
}

export interface PeopleResponse {
  people: Person[];
}

export function getPeople(): Promise<PeopleResponse> {
  return request<PeopleResponse>(
    "/people"
  );
}

export function getPerson(
  personId: string
): Promise<PersonDetail> {
  return request<PersonDetail>(
    `/people/${personId}`
  );
}
