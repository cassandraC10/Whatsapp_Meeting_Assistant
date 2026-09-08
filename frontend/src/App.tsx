import {
  useEffect,
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import {
  createCall,
  deleteCall,
  finishCallRecording,
  getCall,
  getCallNotes,
  getCalls,
  getCallTranscript,
  getRecordingStatus,
  pauseCallRecording,
  processCall,
  resumeCallRecording,
  searchCalls,
  askTca,
  startCallRecording,
  getCallTasks,
  updateCallTask,
  deleteCallTask,
} from "./api";

import type {
  AskResponse,
  Call,
  CallNotes,
  SearchResult,
  Task,
} from "./api";


type View =
  | "calls"
  | "ask"
  | "consent"
  | "recording"
  | "processing"
  | "detail";

type Theme =
  | "light"
  | "dark";


function formatDuration(
  seconds: number
) {
  const totalSeconds =
    Math.max(
      0,
      Math.round(seconds)
    );

  const minutes =
    Math.floor(
      totalSeconds / 60
    );

  const remainingSeconds =
    totalSeconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }

  return (
    `${minutes}m `
    + `${remainingSeconds}s`
  );
}


function formatTimer(
  seconds: number
) {
  const totalSeconds =
    Math.max(
      0,
      Math.round(seconds)
    );

  const hours =
    Math.floor(
      totalSeconds / 3600
    );

  const minutes =
    Math.floor(
      (
        totalSeconds
        % 3600
      ) / 60
    );

  const remainingSeconds =
    totalSeconds % 60;

  if (hours > 0) {
    return [
      hours,
      minutes,
      remainingSeconds,
    ]
      .map(
        (value) =>
          String(value)
            .padStart(
              2,
              "0"
            )
      )
      .join(":");
  }

  return [
    minutes,
    remainingSeconds,
  ]
    .map(
      (value) =>
        String(value)
          .padStart(
            2,
            "0"
          )
    )
    .join(":");
}


function formatDate(
  value: string
) {
  return (
    new Intl.DateTimeFormat(
      "en",
      {
        day: "numeric",
        month: "short",
        year: "numeric",
      }
    )
      .format(
        new Date(value)
      )
  );
}


function getInitialTheme():
Theme {
  const savedTheme =
    localStorage.getItem(
      "tca-theme"
    );

  if (
    savedTheme === "light"
    || savedTheme === "dark"
  ) {
    return savedTheme;
  }

  return "dark";
}


function buildShareableNotes(
  call: Call,
  notes: CallNotes
) {
  const sections: string[] =
    [];

  sections.push(
    `*${
      notes.title
      || call.title
    }*`
  );

  sections.push(
    `\n*Summary*\n${
      notes.summary
    }`
  );

  if (
    notes.key_points.length
    > 0
  ) {
    sections.push(
      "\n*Key points*\n"
      + notes.key_points
        .map(
          (item) =>
            `• ${item}`
        )
        .join("\n")
    );
  }

  if (
    notes.decisions.length
    > 0
  ) {
    sections.push(
      "\n*Decisions*\n"
      + notes.decisions
        .map(
          (item) =>
            `• ${
              item.decision
            }`
        )
        .join("\n")
    );
  }

  if (
    notes
      .my_action_items
      .length > 0
    || notes
      .their_action_items
      .length > 0
  ) {
    const lines: string[] =
      [];

    if (
      notes
        .my_action_items
        .length > 0
    ) {
      lines.push(
        "*My next steps*"
      );

      lines.push(
        ...notes
          .my_action_items
          .map(
            (item) =>
              `• ${item.task}${
                item.deadline
                  ? (
                    ` — ${
                      item.deadline
                    }`
                  )
                  : ""
              }`
          )
      );
    }

    if (
      notes
        .their_action_items
        .length > 0
    ) {
      if (
        lines.length > 0
      ) {
        lines.push("");
      }

      lines.push(
        "*Their next steps*"
      );

      lines.push(
        ...notes
          .their_action_items
          .map(
            (item) =>
              `• ${item.task}${
                item.deadline
                  ? (
                    ` — ${
                      item.deadline
                    }`
                  )
                  : ""
              }`
          )
      );
    }

    sections.push(
      "\n*Next steps*\n"
      + lines.join("\n")
    );
  }

  if (
    notes
      .important_dates
      .length > 0
  ) {
    sections.push(
      "\n*Important dates*\n"
      + notes
        .important_dates
        .map(
          (item) =>
            `• ${item}`
        )
        .join("\n")
    );
  }

  if (
    notes.follow_up
  ) {
    sections.push(
      "\n*Follow-up*\n"
      + notes.follow_up
    );
  }

  return sections.join(
    "\n"
  );
}


function buildDownloadNotes(
  call: Call,
  notes: CallNotes
) {
  return (
    buildShareableNotes(
      call,
      notes
    )
      .replace(
        /\*/g,
        ""
      )
  );
}


function safeFilename(
  value: string
) {
  const clean =
    value
      .trim()
      .replace(
        /[<>:"/\\|?*]/g,
        ""
      )
      .replace(
        /\s+/g,
        "_"
      );

  return (
    clean
    || "call_notes"
  );
}


function formatMatchLabel(
  value: string
) {
  const labels:
  Record<string, string> = {
    title:
      "Title",

    summary:
      "Summary",

    key_points:
      "Key points",

    decisions:
      "Decisions",

    my_action_items:
      "My next steps",

    their_action_items:
      "Their next steps",

    important_dates:
      "Important dates",

    follow_up:
      "Follow-up",

    transcript:
      "Transcript",
  };

  return (
    labels[value]
    || value
  );
}


function App() {
  const [
    theme,
    setTheme,
  ] = useState<Theme>(
    getInitialTheme
  );

  const [
    view,
    setView,
  ] = useState<View>(
    "calls"
  );

  const [
    calls,
    setCalls,
  ] = useState<Call[]>(
    []
  );

  const [
    title,
    setTitle,
  ] = useState("");

  const [
    loadingCalls,
    setLoadingCalls,
  ] = useState(true);

  const [
    creating,
    setCreating,
  ] = useState(false);

  const [
    message,
    setMessage,
  ] = useState("");

  const [
    selectedCall,
    setSelectedCall,
  ] = useState<Call | null>(
    null
  );

  const [
    selectedNotes,
    setSelectedNotes,
  ] = useState<CallNotes | null>(
    null
  );

  const [
    selectedTranscript,
    setSelectedTranscript,
  ] = useState<string | null>(
    null
  );

  const [
    loadingDetail,
    setLoadingDetail,
  ] = useState(false);

  const [
    detailError,
    setDetailError,
  ] = useState("");

  const [
    transcriptOpen,
    setTranscriptOpen,
  ] = useState(false);

  const [
    consentConfirmed,
    setConsentConfirmed,
  ] = useState(false);

  const [
    startingRecording,
    setStartingRecording,
  ] = useState(false);

  const [
    finishingRecording,
    setFinishingRecording,
  ] = useState(false);

  const [
    changingPauseState,
    setChangingPauseState,
  ] = useState(false);

  const [
    elapsedSeconds,
    setElapsedSeconds,
  ] = useState(0);

  const [
    recordingError,
    setRecordingError,
  ] = useState("");

  const [
    processing,
    setProcessing,
  ] = useState(false);

  const [
    processingError,
    setProcessingError,
  ] = useState("");

  const [
    processingSeconds,
    setProcessingSeconds,
  ] = useState(0);

  const [
    actionMessage,
    setActionMessage,
  ] = useState("");

  const [
    deletingCall,
    setDeletingCall,
  ] = useState(false);


  const [
    selectedTasks,
    setSelectedTasks,
  ] = useState<Task[]>([]);

  const [
    tasksLoading,
    setTasksLoading,
  ] = useState(false);

  const [
    tasksError,
    setTasksError,
  ] = useState("");

  const [
    taskBusyId,
    setTaskBusyId,
  ] = useState<string | null>(null);


  /*
   * V3 SEARCH
   */

  const [
    searchQuery,
    setSearchQuery,
  ] = useState("");

  const [
    searchResults,
    setSearchResults,
  ] = useState<SearchResult[]>(
    []
  );

  const [
    searching,
    setSearching,
  ] = useState(false);

  const [
    searchError,
    setSearchError,
  ] = useState("");


  const searchActive =
    searchQuery
      .trim()
      .length > 0;


  /*
   * FEATURE 1 — ASK TCA
   */

  const [
    askQuestion,
    setAskQuestion,
  ] = useState("");

  const [
    askResult,
    setAskResult,
  ] = useState<AskResponse | null>(
    null
  );

  const [
    asking,
    setAsking,
  ] = useState(false);

  const [
    askError,
    setAskError,
  ] = useState("");


  useEffect(() => {
    document
      .documentElement
      .setAttribute(
        "data-theme",
        theme
      );

    localStorage.setItem(
      "tca-theme",
      theme
    );
  }, [
    theme,
  ]);


  useEffect(() => {
    loadCalls();
  }, []);


  useEffect(() => {
    const cleanQuery =
      searchQuery.trim();

    if (!cleanQuery) {
      setSearchResults(
        []
      );

      setSearchError("");

      setSearching(false);

      return;
    }

    let cancelled =
      false;

    const timeout =
      window.setTimeout(
        async () => {
          setSearching(
            true
          );

          setSearchError(
            ""
          );

          try {
            const result =
              await searchCalls(
                cleanQuery
              );

            if (
              cancelled
            ) {
              return;
            }

            setSearchResults(
              result.results
            );

          } catch (error) {
            if (
              cancelled
            ) {
              return;
            }

            setSearchResults(
              []
            );

            setSearchError(
              error instanceof Error
                ? error.message
                : (
                  "Could not search "
                  + "conversations."
                )
            );

          } finally {
            if (
              !cancelled
            ) {
              setSearching(
                false
              );
            }
          }
        },
        250
      );

    return () => {
      cancelled = true;

      window.clearTimeout(
        timeout
      );
    };

  }, [
    searchQuery,
  ]);


  useEffect(() => {
    if (
      view !== "recording"
      || !selectedCall
    ) {
      return;
    }

    let stopped =
      false;

    async function pollStatus() {
      try {
        const result =
          await getRecordingStatus(
            selectedCall!.id
          );

        if (
          stopped
        ) {
          return;
        }

        setElapsedSeconds(
          result.elapsed_seconds
        );

        setSelectedCall(
          (current) => {
            if (!current) {
              return current;
            }

            if (
              current.status
                === result.status
              && (
                current
                  .failure_reason
                === (
                  result
                    .failure_reason
                )
              )
            ) {
              return current;
            }

            return {
              ...current,

              status:
                result.status,

              failure_reason:
                result
                  .failure_reason,
            };
          }
        );

        setRecordingError(
          ""
        );

      } catch (error) {
        if (
          stopped
        ) {
          return;
        }

        setRecordingError(
          error instanceof Error
            ? error.message
            : (
              "Could not check "
              + "recording status."
            )
        );
      }
    }

    pollStatus();

    const interval =
      window.setInterval(
        pollStatus,
        1000
      );

    return () => {
      stopped = true;

      window.clearInterval(
        interval
      );
    };

  }, [
    view,
    selectedCall?.id,
  ]);


  useEffect(() => {
    if (
      view !== "processing"
      || !processing
    ) {
      return;
    }

    const interval =
      window.setInterval(
        () => {
          setProcessingSeconds(
            (current) =>
              current + 1
          );
        },
        1000
      );

    return () => {
      window.clearInterval(
        interval
      );
    };

  }, [
    view,
    processing,
  ]);


  function toggleTheme() {
    setTheme(
      (current) =>
        current === "dark"
          ? "light"
          : "dark"
    );
  }


  function clearSearch() {
    setSearchQuery(
      ""
    );

    setSearchResults(
      []
    );

    setSearchError(
      ""
    );
  }


  function openAskView(
    call?: Call
  ) {
    setAskError("");
    setAskResult(null);

    if (call) {
      setSelectedCall(call);
    } else {
      setSelectedCall(null);
    }

    setView("ask");
  }


  function clearAsk() {
    setAskQuestion("");
    setAskResult(null);
    setAskError("");
  }


  async function submitAsk(
    event: FormEvent
  ) {
    event.preventDefault();

    const cleanQuestion =
      askQuestion.trim();

    if (
      !cleanQuestion
      || asking
    ) {
      return;
    }

    setAsking(true);
    setAskError("");

    try {
      const result =
        await askTca(
          cleanQuestion,
          selectedCall?.id
        );

      setAskResult(result);

    } catch (error) {
      setAskError(
        error instanceof Error
          ? error.message
          : (
            "Could not ask TCA "
            + "right now."
          )
      );

    } finally {
      setAsking(false);
    }
  }


  async function openSourceCall(
    callId: string
  ) {
    const call =
      calls.find(
        (item) =>
          item.id === callId
      );

    if (call) {
      await openCall(call);
      return;
    }

    try {
      const fetchedCall =
        await getCall(callId);

      setCalls(
        (current) => [
          fetchedCall,
          ...current.filter(
            (item) =>
              item.id !== callId
          ),
        ]
      );

      await openCall(fetchedCall);

    } catch (error) {
      setAskError(
        error instanceof Error
          ? error.message
          : (
            "Could not open "
            + "that conversation."
          )
      );
    }
  }


  async function loadCalls() {
    setLoadingCalls(
      true
    );

    try {
      const result =
        await getCalls();

      setCalls(
        result
      );

      setMessage(
        ""
      );

    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : (
            "Could not load "
            + "conversations."
          )
      );

    } finally {
      setLoadingCalls(
        false
      );
    }
  }


  function updateCallInList(
    updatedCall: Call
  ) {
    setCalls(
      (current) =>
        current.map(
          (call) =>
            call.id
              === updatedCall.id
              ? updatedCall
              : call
        )
    );
  }


  async function handleSubmit(
    event: FormEvent
  ) {
    event.preventDefault();

    if (
      creating
    ) {
      return;
    }

    setCreating(
      true
    );

    setMessage(
      ""
    );

    try {
      const call =
        await createCall(
          title
        );

      setCalls(
        (current) => [
          call,
          ...current,
        ]
      );

      setSelectedCall(
        call
      );

      setTitle(
        ""
      );

      setConsentConfirmed(
        false
      );

      setRecordingError(
        ""
      );

      setElapsedSeconds(
        0
      );

      setView(
        "consent"
      );

    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : (
            "Could not create "
            + "the call."
          )
      );

    } finally {
      setCreating(
        false
      );
    }
  }


  async function loadCompletedCall(
    callId: string
  ) {
    setLoadingDetail(
      true
    );

    setDetailError(
      ""
    );

    setActionMessage(
      ""
    );

    try {
      setTasksLoading(true);
      setTasksError("");

      const [
        updatedCall,
        notesResult,
        transcriptResult,
        tasksResult,
      ] =
        await Promise.all([
          getCall(
            callId
          ),

          getCallNotes(
            callId
          ),

          getCallTranscript(
            callId
          ),

          getCallTasks(
            callId
          ),
        ]);

      setSelectedCall(
        updatedCall
      );

      setSelectedNotes(
        notesResult.notes
      );

      setSelectedTranscript(
        transcriptResult
          .transcript
      );

      setSelectedTasks(
        tasksResult.tasks
      );

      updateCallInList(
        updatedCall
      );

      setTranscriptOpen(
        false
      );

      setView(
        "detail"
      );

    } catch (error) {
      setTasksError(
        error instanceof Error
          ? error.message
          : "Could not load next steps."
      );

      setDetailError(
        error instanceof Error
          ? error.message
          : (
            "Could not load "
            + "this call."
          )
      );

      setView(
        "detail"
      );

    } finally {
      setTasksLoading(false);
      setLoadingDetail(
        false
      );
    }
  }


  async function updateTaskState(
    taskId: string,
    changes: {
      task?: string;
      deadline?: string | null;
      completed?: boolean;
    }
  ) {
    if (!selectedCall) {
      return;
    }

    setTaskBusyId(taskId);
    setTasksError("");

    try {
      const updatedTask = await updateCallTask(
        selectedCall.id,
        taskId,
        changes
      );

      setSelectedTasks((current) =>
        current.map((task) =>
          task.id === updatedTask.id
            ? updatedTask
            : task
        )
      );
    } catch (error) {
      setTasksError(
        error instanceof Error
          ? error.message
          : "Could not update that task."
      );
      throw error;
    } finally {
      setTaskBusyId(null);
    }
  }


  async function removeTask(
    taskId: string
  ) {
    if (!selectedCall) {
      return;
    }

    setTaskBusyId(taskId);
    setTasksError("");

    try {
      await deleteCallTask(
        selectedCall.id,
        taskId
      );

      setSelectedTasks((current) =>
        current.filter((task) => task.id !== taskId)
      );
    } catch (error) {
      setTasksError(
        error instanceof Error
          ? error.message
          : "Could not delete that task."
      );
      throw error;
    } finally {
      setTaskBusyId(null);
    }
  }


  async function openCall(
    call: Call
  ) {
    setSelectedCall(
      call
    );

    setSelectedNotes(
      null
    );

    setSelectedTranscript(
      null
    );

    setSelectedTasks([]);
    setTasksError("");
    setTasksLoading(false);

    setTranscriptOpen(
      false
    );

    setDetailError(
      ""
    );

    setActionMessage(
      ""
    );

    if (
      call.status
        === "completed"
    ) {
      await loadCompletedCall(
        call.id
      );

      return;
    }

    setView(
      "detail"
    );
  }


  function returnToCalls() {
    setView(
      "calls"
    );

    setSelectedCall(
      null
    );

    setSelectedNotes(
      null
    );

    setSelectedTranscript(
      null
    );

    setTranscriptOpen(
      false
    );

    setDetailError(
      ""
    );

    setRecordingError(
      ""
    );

    setProcessingError(
      ""
    );

    setActionMessage(
      ""
    );

    setConsentConfirmed(
      false
    );

    setElapsedSeconds(
      0
    );

    setProcessingSeconds(
      0
    );

    setAskQuestion("");
    setAskResult(null);
    setAskError("");

    loadCalls();
  }


  function continueCreatedCall(
    call: Call
  ) {
    setSelectedCall(
      call
    );

    setConsentConfirmed(
      false
    );

    setRecordingError(
      ""
    );

    setElapsedSeconds(
      0
    );

    setView(
      "consent"
    );
  }


  async function beginRecording() {
    if (
      !selectedCall
      || !consentConfirmed
      || startingRecording
    ) {
      return;
    }

    setStartingRecording(
      true
    );

    setRecordingError(
      ""
    );

    try {
      const updatedCall =
        await startCallRecording(
          selectedCall.id
        );

      setSelectedCall(
        updatedCall
      );

      updateCallInList(
        updatedCall
      );

      setElapsedSeconds(
        0
      );

      setView(
        "recording"
      );

    } catch (error) {
      setRecordingError(
        error instanceof Error
          ? error.message
          : (
            "Could not start "
            + "recording."
          )
      );

    } finally {
      setStartingRecording(
        false
      );
    }
  }


  async function togglePause() {
    if (
      !selectedCall
      || changingPauseState
      || finishingRecording
    ) {
      return;
    }

    setChangingPauseState(
      true
    );

    setRecordingError(
      ""
    );

    try {
      const updatedCall =
        selectedCall.status
          === "paused"
          ? (
            await resumeCallRecording(
              selectedCall.id
            )
          )
          : (
            await pauseCallRecording(
              selectedCall.id
            )
          );

      setSelectedCall(
        updatedCall
      );

      updateCallInList(
        updatedCall
      );

    } catch (error) {
      setRecordingError(
        error instanceof Error
          ? error.message
          : (
            "Could not change "
            + "recording state."
          )
      );

    } finally {
      setChangingPauseState(
        false
      );
    }
  }


  async function finishRecording() {
    if (
      !selectedCall
      || finishingRecording
    ) {
      return;
    }

    setFinishingRecording(
      true
    );

    setRecordingError(
      ""
    );

    try {
      const result =
        await finishCallRecording(
          selectedCall.id
        );

      setSelectedCall(
        result.call
      );

      updateCallInList(
        result.call
      );

      setElapsedSeconds(
        result
          .recording
          .duration_seconds
      );

      setSelectedNotes(
        null
      );

      setSelectedTranscript(
        null
      );

      setProcessingError(
        ""
      );

      setProcessingSeconds(
        0
      );

      setView(
        "processing"
      );

      await runProcessing(
        result.call
      );

    } catch (error) {
      setRecordingError(
        error instanceof Error
          ? error.message
          : (
            "Could not finish "
            + "recording."
          )
      );

    } finally {
      setFinishingRecording(
        false
      );
    }
  }


  async function runProcessing(
    call: Call
  ) {
    if (
      processing
    ) {
      return;
    }

    setSelectedCall(
      call
    );

    setProcessing(
      true
    );

    setProcessingError(
      ""
    );

    setProcessingSeconds(
      0
    );

    setView(
      "processing"
    );

    try {
      await processCall(
        call.id
      );

      const updatedCall =
        await getCall(
          call.id
        );

      setSelectedCall(
        updatedCall
      );

      updateCallInList(
        updatedCall
      );

      if (
        updatedCall.status
          !== "completed"
      ) {
        throw new Error(
          "Processing finished, "
          + "but the call was not "
          + "marked complete."
        );
      }

      await loadCompletedCall(
        call.id
      );

    } catch (error) {
      setProcessingError(
        error instanceof Error
          ? error.message
          : (
            "We couldn't prepare "
            + "your notes."
          )
      );

      try {
        const updatedCall =
          await getCall(
            call.id
          );

        setSelectedCall(
          updatedCall
        );

        updateCallInList(
          updatedCall
        );

      } catch {
        // Keep current call.
      }

      setView(
        "processing"
      );

    } finally {
      setProcessing(
        false
      );
    }
  }


  async function handleDeleteCall() {
    if (
      !selectedCall
      || deletingCall
    ) {
      return;
    }

    const confirmed =
      window.confirm(
        `Delete "${
          selectedCall.title
        }"?\n\n`
        + (
          "This will permanently "
          + "remove the recording, "
          + "transcript and notes."
        )
      );

    if (
      !confirmed
    ) {
      return;
    }

    setDeletingCall(
      true
    );

    setActionMessage(
      ""
    );

    setDetailError(
      ""
    );

    try {
      await deleteCall(
        selectedCall.id
      );

      setCalls(
        (current) =>
          current.filter(
            (call) =>
              call.id
                !== selectedCall.id
          )
      );

      setSelectedCall(
        null
      );

      setSelectedNotes(
        null
      );

      setSelectedTranscript(
        null
      );

      setView(
        "calls"
      );

      setMessage(
        "Conversation deleted."
      );

      await loadCalls();

      if (
        searchActive
      ) {
        const result =
          await searchCalls(
            searchQuery
          );

        setSearchResults(
          result.results
        );
      }

    } catch (error) {
      setDetailError(
        error instanceof Error
          ? error.message
          : (
            "Could not delete "
            + "this conversation."
          )
      );

    } finally {
      setDeletingCall(
        false
      );
    }
  }


  async function copyNotes() {
    if (
      !selectedCall
      || !selectedNotes
    ) {
      return;
    }

    const text =
      buildDownloadNotes(
        selectedCall,
        selectedNotes
      );

    try {
      await navigator
        .clipboard
        .writeText(
          text
        );

      setActionMessage(
        "Notes copied."
      );

    } catch {
      setActionMessage(
        "Could not copy notes."
      );
    }
  }


  function downloadNotes() {
    if (
      !selectedCall
      || !selectedNotes
    ) {
      return;
    }

    const text =
      buildDownloadNotes(
        selectedCall,
        selectedNotes
      );

    const blob =
      new Blob(
        [
          text,
        ],
        {
          type:
            "text/plain;"
            + "charset=utf-8",
        }
      );

    const url =
      URL.createObjectURL(
        blob
      );

    const link =
      document.createElement(
        "a"
      );

    link.href =
      url;

    link.download =
      `${
        safeFilename(
          selectedCall.title
        )
      }_notes.txt`;

    document.body
      .appendChild(
        link
      );

    link.click();

    link.remove();

    URL.revokeObjectURL(
      url
    );

    setActionMessage(
      "Notes downloaded."
    );
  }


  function shareToWhatsApp() {
    if (
      !selectedCall
      || !selectedNotes
    ) {
      return;
    }

    const text =
      buildShareableNotes(
        selectedCall,
        selectedNotes
      );

    const url =
      "https://wa.me/?text="
      + encodeURIComponent(
        text
      );

    window.open(
      url,
      "_blank",
      "noopener,noreferrer"
    );

    setActionMessage(
      "WhatsApp opened "
      + "with your notes."
    );
  }


  if (
    view === "ask"
  ) {
    return (
      <AskTcaView
        theme={theme}
        question={askQuestion}
        result={askResult}
        asking={asking}
        error={askError}
        selectedCall={selectedCall}
        onQuestionChange={
          setAskQuestion
        }
        onSubmit={
          submitAsk
        }
        onClear={
          clearAsk
        }
        onBack={
          returnToCalls
        }
        onToggleTheme={
          toggleTheme
        }
        onOpenSource={
          openSourceCall
        }
      />
    );
  }


  if (
    view === "consent"
    && selectedCall
  ) {
    return (
      <ConsentView
        call={selectedCall}
        theme={theme}
        confirmed={
          consentConfirmed
        }
        starting={
          startingRecording
        }
        error={
          recordingError
        }
        onToggleTheme={
          toggleTheme
        }
        onConfirmedChange={
          setConsentConfirmed
        }
        onStart={
          beginRecording
        }
        onBack={
          returnToCalls
        }
      />
    );
  }


  if (
    view === "recording"
    && selectedCall
  ) {
    return (
      <RecordingView
        call={selectedCall}
        theme={theme}
        elapsedSeconds={
          elapsedSeconds
        }
        finishing={
          finishingRecording
        }
        changingPauseState={
          changingPauseState
        }
        error={
          recordingError
        }
        onToggleTheme={
          toggleTheme
        }
        onPauseResume={
          togglePause
        }
        onFinish={
          finishRecording
        }
      />
    );
  }


  if (
    view === "processing"
    && selectedCall
  ) {
    return (
      <ProcessingView
        call={selectedCall}
        theme={theme}
        seconds={
          processingSeconds
        }
        processing={
          processing
        }
        error={
          processingError
        }
        onToggleTheme={
          toggleTheme
        }
        onRetry={() =>
          runProcessing(
            selectedCall
          )
        }
        onBack={
          returnToCalls
        }
      />
    );
  }


  if (
    view === "detail"
    && selectedCall
  ) {
    return (
      <CallDetail
        call={selectedCall}
        notes={selectedNotes}
        transcript={
          selectedTranscript
        }
        loading={
          loadingDetail
        }
        error={
          detailError
        }
        transcriptOpen={
          transcriptOpen
        }
        theme={theme}
        actionMessage={
          actionMessage
        }
        deleting={
          deletingCall
        }
        tasks={selectedTasks}
        tasksLoading={tasksLoading}
        tasksError={tasksError}
        taskBusyId={taskBusyId}
        onUpdateTask={updateTaskState}
        onDeleteTask={removeTask}
        onToggleTheme={
          toggleTheme
        }
        onToggleTranscript={() =>
          setTranscriptOpen(
            (current) =>
              !current
          )
        }
        onAskAboutCall={() =>
          openAskView(
            selectedCall
          )
        }
        onBack={
          returnToCalls
        }
        onContinueCreatedCall={() =>
          continueCreatedCall(
            selectedCall
          )
        }
        onProcessCall={() =>
          runProcessing(
            selectedCall
          )
        }
        onCopy={
          copyNotes
        }
        onDownload={
          downloadNotes
        }
        onWhatsApp={
          shareToWhatsApp
        }
        onDelete={
          handleDeleteCall
        }
      />
    );
  }


  return (
    <main className="app-shell">
      <TopBar
        theme={theme}
        onToggleTheme={
          toggleTheme
        }
      />

      <section className="workspace">
        <div className="page-heading">
          <div>
            <h1>
              Calls
            </h1>

            <p>
              Conversations worth
              remembering.
            </p>
          </div>
        </div>


        <section className="conversation-search">
          <span className="section-label">
            Find a conversation
          </span>

          <div className="search-field">
            <span
              className="search-icon"
              aria-hidden="true"
            >
              ⌕
            </span>

            <input
              type="search"
              value={
                searchQuery
              }
              onChange={
                (event) =>
                  setSearchQuery(
                    event.target.value
                  )
              }
              placeholder={
                "Search conversations"
              }
              aria-label={
                "Search conversations"
              }
              autoComplete="off"
            />

            {searchActive && (
              <button
                type="button"
                className="search-clear"
                onClick={
                  clearSearch
                }
                aria-label={
                  "Clear search"
                }
              >
                ×
              </button>
            )}
          </div>
        </section>


        {!searchActive && (
          <>
            <AskTcaEntry
              onOpen={() =>
                openAskView()
              }
            />

            <form
              className="call-composer"
            onSubmit={
              handleSubmit
            }
          >
            <div className="composer-copy">
              <span className="section-label">
                New call
              </span>

              <label
                htmlFor="call-title"
              >
                What is this call about?
              </label>
            </div>

            <div className="composer-row">
              <input
                id="call-title"
                value={
                  title
                }
                onChange={
                  (event) =>
                    setTitle(
                      event
                        .target
                        .value
                    )
                }
                placeholder={
                  "Product feedback "
                  + "with Jane"
                }
                maxLength={
                  120
                }
              />

              <button
                className="primary-button"
                type="submit"
                disabled={
                  creating
                }
              >
                {creating
                  ? "Starting…"
                  : "Start call"}
              </button>
            </div>
            </form>
          </>
        )}


        {message
          && !searchActive
          && (
            <p className="system-message">
              {message}
            </p>
          )}


        {searchActive ? (
          <SearchResultsView
            query={
              searchQuery
            }
            results={
              searchResults
            }
            searching={
              searching
            }
            error={
              searchError
            }
            onOpenCall={
              openCall
            }
            onClear={
              clearSearch
            }
          />

        ) : (
          <section className="history">
            <div className="history-heading">
              <div>
                <span className="section-label">
                  Recent conversations
                </span>

                <h2>
                  Your calls
                </h2>
              </div>

              <span className="call-count">
                {calls.length}
              </span>
            </div>

            {loadingCalls ? (
              <p className="empty-state">
                Loading conversations…
              </p>

            ) : calls.length
              === 0 ? (
                <p className="empty-state">
                  No calls yet. Your
                  conversations will
                  appear here.
                </p>

              ) : (
                <div className="call-list">
                  {calls.map(
                    (call) => (
                      <CallRow
                        key={
                          call.id
                        }
                        call={
                          call
                        }
                        onOpen={() =>
                          openCall(
                            call
                          )
                        }
                      />
                    )
                  )}
                </div>
              )}
          </section>
        )}
      </section>
    </main>
  );
}


function AskTcaEntry({
  onOpen,
}: {
  onOpen: () => void;
}) {
  return (
    <section className="ask-entry">
      <div className="ask-entry-copy">
        <span className="section-label">
          Ask TCA
        </span>

        <h2>
          What do you want to remember?
        </h2>

        <p>
          Ask a question across your
          saved conversations.
        </p>
      </div>

      <button
        type="button"
        className="secondary-button"
        onClick={onOpen}
      >
        Ask TCA
      </button>
    </section>
  );
}


function AskTcaView({
  theme,
  question,
  result,
  asking,
  error,
  selectedCall,
  onQuestionChange,
  onSubmit,
  onClear,
  onBack,
  onToggleTheme,
  onOpenSource,
}: {
  theme: Theme;
  question: string;
  result: AskResponse | null;
  asking: boolean;
  error: string;
  selectedCall: Call | null;

  onQuestionChange:
    (value: string) => void;

  onSubmit:
    (event: FormEvent) => void;

  onClear:
    () => void;

  onBack:
    () => void;

  onToggleTheme:
    () => void;

  onOpenSource:
    (callId: string) => void;
}) {
  const scoped =
    Boolean(selectedCall);

  return (
    <main className="app-shell">
      <TopBar
        theme={theme}
        onToggleTheme={onToggleTheme}
      />

      <section className="ask-shell">
        <button
          type="button"
          className="back-button"
          onClick={onBack}
        >
          ← Calls
        </button>

        <div className="ask-header">
          <span className="section-label">
            {scoped
              ? "Ask about this call"
              : "Ask TCA"}
          </span>

          <h1>
            {scoped
              ? selectedCall?.title
              : "What do you want to remember?"}
          </h1>

          <p>
            {scoped
              ? (
                "Ask anything about "
                + "this conversation."
              )
              : (
                "Ask a question and TCA "
                + "will look through your "
                + "saved conversations."
              )}
          </p>
        </div>

        <form
          className="ask-form"
          onSubmit={onSubmit}
        >
          <label
            htmlFor="ask-question"
            className="section-label"
          >
            Your question
          </label>

          <textarea
            id="ask-question"
            value={question}
            onChange={(event) =>
              onQuestionChange(
                event.target.value
              )
            }
            placeholder={
              scoped
                ? (
                  "What did we agree "
                  + "about the launch?"
                )
                : (
                  "What did Ayo say "
                  + "about onboarding?"
                )
            }
            rows={3}
            maxLength={1000}
            autoFocus
          />

          <div className="ask-form-footer">
            <span className="ask-scope">
              {scoped
                ? "This conversation only"
                : "All saved conversations"}
            </span>

            <div className="ask-form-actions">
              {(question.trim() || result) && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={onClear}
                  disabled={asking}
                >
                  Clear
                </button>
              )}

              <button
                type="submit"
                className="primary-button"
                disabled={
                  asking
                  || !question.trim()
                }
              >
                {asking
                  ? "Thinking…"
                  : "Ask TCA"}
              </button>
            </div>
          </div>
        </form>

        {error && (
          <div className="notice notice-error ask-notice">
            <strong>
              TCA couldn't answer that.
            </strong>

            <p>{error}</p>
          </div>
        )}

        {asking && (
          <div className="ask-loading">
            <span className="ask-loading-dot" />
            <span>
              Looking through your
              conversations…
            </span>
          </div>
        )}

        {!asking && result && (
          <AskAnswer
            result={result}
            onOpenSource={onOpenSource}
          />
        )}
      </section>
    </main>
  );
}


function AskAnswer({
  result,
  onOpenSource,
}: {
  result: AskResponse;
  onOpenSource:
    (callId: string) => void;
}) {
  return (
    <section className="ask-answer">
      <div className="ask-answer-header">
        <span className="section-label">
          Answer
        </span>

        {!result.found_answer && (
          <span className="ask-answer-state">
            No match
          </span>
        )}
      </div>

      <div className="ask-answer-body">
        <p>{result.answer}</p>
      </div>

      {result.sources.length > 0 && (
        <div className="ask-sources">
          <div className="ask-sources-heading">
            <span className="section-label">
              From your conversations
            </span>

            <span className="ask-source-count">
              {result.sources.length}
            </span>
          </div>

          <div className="ask-source-list">
            {result.sources.map(
              (source) => (
                <button
                  type="button"
                  className="ask-source"
                  key={source.call_id}
                  onClick={() =>
                    onOpenSource(
                      source.call_id
                    )
                  }
                >
                  <div className="ask-source-main">
                    <h3>{source.title}</h3>

                    <div className="ask-source-meta">
                      {formatDate(
                        source.created_at
                      )}
                    </div>

                    {source.snippet && (
                      <p>
                        {source.snippet}
                      </p>
                    )}
                  </div>

                  <span className="call-arrow">
                    →
                  </span>
                </button>
              )
            )}
          </div>
        </div>
      )}

      {result.sources.length === 0
        && result.found_answer && (
          <p className="ask-source-note">
            No source conversation was
            returned with this answer.
          </p>
        )}
    </section>
  );
}


function SearchResultsView({
  query,
  results,
  searching,
  error,
  onOpenCall,
  onClear,
}: {
  query: string;
  results: SearchResult[];
  searching: boolean;
  error: string;

  onOpenCall:
    (call: Call) => void;

  onClear:
    () => void;
}) {
  return (
    <section className="history search-results">
      <div className="history-heading">
        <div>
          <span className="section-label">
            Search results
          </span>

          <h2>
            {searching
              ? "Searching…"
              : (
                `${results.length} ${
                  results.length
                    === 1
                    ? "conversation"
                    : "conversations"
                }`
              )}
          </h2>
        </div>

        {!searching && (
          <button
            type="button"
            className="search-reset-button"
            onClick={
              onClear
            }
          >
            Clear
          </button>
        )}
      </div>


      {error && (
        <div className="notice notice-error">
          <strong>
            Search didn't work.
          </strong>

          <p>
            {error}
          </p>
        </div>
      )}


      {!error
        && searching
        && (
          <p className="empty-state">
            Looking through your
            conversations…
          </p>
        )}


      {!error
        && !searching
        && results.length === 0
        && (
          <div className="search-empty">
            <strong>
              No conversations found.
            </strong>

            <p>
              Nothing matched
              “{query.trim()}”.
              Try another word
              or phrase.
            </p>
          </div>
        )}


      {!error
        && !searching
        && results.length > 0
        && (
          <div className="search-result-list">
            {results.map(
              (result) => (
                <button
                  type="button"
                  className="search-result-row"
                  key={
                    result.call.id
                  }
                  onClick={() =>
                    onOpenCall(
                      result.call
                    )
                  }
                >
                  <div className="search-result-top">
                    <div>
                      <h3>
                        {
                          result
                            .call
                            .title
                        }
                      </h3>

                      <div className="call-meta">
                        <span>
                          {formatDate(
                            result
                              .call
                              .created_at
                          )}
                        </span>

                        <span>
                          {formatDuration(
                            result
                              .call
                              .duration_seconds
                          )}
                        </span>

                        <span
                          className={
                            `status `
                            + (
                              `status-${
                                result
                                  .call
                                  .status
                              }`
                            )
                          }
                        >
                          {
                            result
                              .call
                              .status
                          }
                        </span>
                      </div>
                    </div>

                    <span className="call-arrow">
                      →
                    </span>
                  </div>

                  {result.snippet && (
                    <p className="search-snippet">
                      {result.snippet}
                    </p>
                  )}

                  {result
                    .matched_in
                    .length > 0
                    && (
                      <div className="search-match-source">
                        Found in{" "}
                        {
                          result
                            .matched_in
                            .slice(
                              0,
                              3
                            )
                            .map(
                              formatMatchLabel
                            )
                            .join(
                              " · "
                            )
                        }
                      </div>
                    )}
                </button>
              )
            )}
          </div>
        )}
    </section>
  );
}


function CallRow({
  call,
  onOpen,
}: {
  call: Call;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      className="call-row"
      onClick={
        onOpen
      }
    >
      <div className="call-date">
        {formatDate(
          call.created_at
        )}
      </div>

      <div className="call-main">
        <h3>
          {call.title}
        </h3>

        <div className="call-meta">
          <span>
            {formatDuration(
              call.duration_seconds
            )}
          </span>

          <span
            className={
              `status `
              + `status-${
                call.status
              }`
            }
          >
            {call.status}
          </span>
        </div>
      </div>

      <span className="call-arrow">
        →
      </span>
    </button>
  );
}


function ConsentView({
  call,
  theme,
  confirmed,
  starting,
  error,
  onToggleTheme,
  onConfirmedChange,
  onStart,
  onBack,
}: {
  call: Call;
  theme: Theme;
  confirmed: boolean;
  starting: boolean;
  error: string;

  onToggleTheme:
    () => void;

  onConfirmedChange:
    (
      confirmed: boolean
    ) => void;

  onStart:
    () => void;

  onBack:
    () => void;
}) {
  return (
    <main className="app-shell">
      <TopBar
        theme={theme}
        onToggleTheme={
          onToggleTheme
        }
      />

      <section className="flow-shell">
        <button
          type="button"
          className="back-button"
          onClick={
            onBack
          }
        >
          ← Calls
        </button>

        <div className="flow-header">
          <span className="section-label">
            Before recording
          </span>

          <h1>
            {call.title}
          </h1>

          <p>
            Make sure everyone
            on the call knows
            they're being recorded.
          </p>
        </div>

        <div className="consent-card">
          <div className="consent-copy">
            <h2>
              Everyone should know.
            </h2>

            <p>
              TCA records your microphone
              and the audio playing through
              your computer so it can
              prepare your notes afterwards.
            </p>
          </div>

          <label className="consent-check">
            <input
              type="checkbox"
              checked={
                confirmed
              }
              onChange={
                (event) =>
                  onConfirmedChange(
                    event
                      .target
                      .checked
                  )
              }
            />

            <span className="check-box" />

            <span>
              I've told everyone on this
              call that I'm recording.
            </span>
          </label>
        </div>

        <div className="flow-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={
              onBack
            }
          >
            Cancel
          </button>

          <button
            type="button"
            className="primary-button"
            disabled={
              !confirmed
              || starting
            }
            onClick={
              onStart
            }
          >
            {starting
              ? "Starting…"
              : "Start recording"}
          </button>
        </div>

        {error && (
          <div className="inline-error">
            {error}
          </div>
        )}

        <p className="flow-footnote">
          Headphones give the cleanest
          speaker separation.
        </p>
      </section>
    </main>
  );
}


function RecordingView({
  call,
  theme,
  elapsedSeconds,
  finishing,
  changingPauseState,
  error,
  onToggleTheme,
  onPauseResume,
  onFinish,
}: {
  call: Call;
  theme: Theme;
  elapsedSeconds: number;
  finishing: boolean;
  changingPauseState: boolean;
  error: string;

  onToggleTheme:
    () => void;

  onPauseResume:
    () => void;

  onFinish:
    () => void;
}) {
  const paused =
    call.status
      === "paused";

  return (
    <main className="app-shell">
      <TopBar
        theme={theme}
        onToggleTheme={
          onToggleTheme
        }
      />

      <section className="recording-shell">
        <div className="recording-heading">
          <span className="section-label">
            Active call
          </span>

          <h1>
            {call.title}
          </h1>
        </div>

        <div className="recording-stage">
          <div className="recording-state">
            {!paused && (
              <span className="live-dot" />
            )}

            <span>
              {paused
                ? "Paused"
                : "Recording"}
            </span>
          </div>

          <div className="recording-timer">
            {formatTimer(
              elapsedSeconds
            )}
          </div>

          <div className="audio-status">
            <div>
              <span
                className={
                  paused
                    ? ""
                    : "audio-indicator"
                }
              />

              <span>
                Your microphone
              </span>

              <strong>
                {paused
                  ? "Paused"
                  : "On"}
              </strong>
            </div>

            <div>
              <span
                className={
                  paused
                    ? ""
                    : "audio-indicator"
                }
              />

              <span>
                Call audio
              </span>

              <strong>
                {paused
                  ? "Paused"
                  : "On"}
              </strong>
            </div>
          </div>
        </div>

        <div className="recording-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={
              onPauseResume
            }
            disabled={
              changingPauseState
              || finishing
            }
          >
            {changingPauseState
              ? "Please wait…"
              : paused
                ? "Resume"
                : "Pause"}
          </button>

          <button
            type="button"
            className="finish-button"
            onClick={
              onFinish
            }
            disabled={
              finishing
              || changingPauseState
            }
          >
            <span className="stop-icon" />

            {finishing
              ? "Finishing…"
              : "Finish call"}
          </button>
        </div>

        {error && (
          <div className="inline-error centered-error">
            {error}
          </div>
        )}

        <div className="recording-note">
          {paused
            ? (
              "Audio while paused "
              + "will not be included."
            )
            : (
              "Keep this window open "
              + "while the call is "
              + "being recorded."
            )}
        </div>
      </section>
    </main>
  );
}


function ProcessingView({
  call,
  theme,
  seconds,
  processing,
  error,
  onToggleTheme,
  onRetry,
  onBack,
}: {
  call: Call;
  theme: Theme;
  seconds: number;
  processing: boolean;
  error: string;

  onToggleTheme:
    () => void;

  onRetry:
    () => void;

  onBack:
    () => void;
}) {
  return (
    <main className="app-shell">
      <TopBar
        theme={theme}
        onToggleTheme={
          onToggleTheme
        }
      />

      <section className="processing-shell">
        <div className="processing-copy">
          <span className="section-label">
            Call saved
          </span>

          <h1>
            {error
              ? "Your recording is safe."
              : "Preparing your notes."}
          </h1>

          <p>
            {error
              ? (
                "Something interrupted "
                + "processing. You don't "
                + "need to record the "
                + "call again."
              )
              : (
                "TCA is working through "
                + "the conversation and "
                + "turning it into a "
                + "useful recap."
              )}
          </p>
        </div>

        {!error && (
          <>
            <div className="processing-indicator">
              <span />
              <span />
              <span />
            </div>

            <div className="processing-status">
              <strong>
                {call.title}
              </strong>

              <span>
                {formatTimer(
                  seconds
                )}
              </span>
            </div>

            <p className="processing-note">
              Longer calls can take a little
              longer. Keep this window open
              while your notes are prepared.
            </p>
          </>
        )}

        {error && (
          <div className="processing-error">
            <strong>
              Processing didn't finish.
            </strong>

            <p>
              {error}
            </p>

            <div className="processing-error-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={
                  onBack
                }
              >
                Back to calls
              </button>

              <button
                type="button"
                className="primary-button"
                disabled={
                  processing
                }
                onClick={
                  onRetry
                }
              >
                {processing
                  ? "Trying again…"
                  : "Try again"}
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}


interface CallDetailProps {
  call: Call;

  notes:
    CallNotes | null;

  transcript:
    string | null;

  loading:
    boolean;

  error:
    string;

  transcriptOpen:
    boolean;

  theme:
    Theme;

  actionMessage:
    string;

  deleting:
    boolean;

  tasks:
    Task[];

  tasksLoading:
    boolean;

  tasksError:
    string;

  taskBusyId:
    string | null;

  onUpdateTask:
    (
      taskId: string,
      changes: {
        task?: string;
        deadline?: string | null;
        completed?: boolean;
      }
    ) => Promise<void>;

  onDeleteTask:
    (taskId: string) => Promise<void>;

  onToggleTheme:
    () => void;

  onToggleTranscript:
    () => void;

  onAskAboutCall:
    () => void;

  onBack:
    () => void;

  onContinueCreatedCall:
    () => void;

  onProcessCall:
    () => void;

  onCopy:
    () => void;

  onDownload:
    () => void;

  onWhatsApp:
    () => void;

  onDelete:
    () => void;
}


function CallDetail({
  call,
  notes,
  transcript,
  loading,
  error,
  transcriptOpen,
  theme,
  actionMessage,
  deleting,
  tasks,
  tasksLoading,
  tasksError,
  taskBusyId,
  onUpdateTask,
  onDeleteTask,
  onToggleTheme,
  onToggleTranscript,
  onAskAboutCall,
  onBack,
  onContinueCreatedCall,
  onProcessCall,
  onCopy,
  onDownload,
  onWhatsApp,
  onDelete,
}: CallDetailProps) {
  const canDelete =
    call.status
      !== "recording"
    && call.status
      !== "paused"
    && call.status
      !== "processing";

  return (
    <main className="app-shell">
      <TopBar
        theme={theme}
        onToggleTheme={
          onToggleTheme
        }
      />

      <article className="recap">
        <button
          type="button"
          className="back-button"
          onClick={
            onBack
          }
        >
          ← Calls
        </button>

        <header className="recap-header">
          <h1>
            {call.title}
          </h1>

          <div className="recap-meta">
            <span>
              {formatDate(
                call.created_at
              )}
            </span>

            <span>
              •
            </span>

            <span>
              {formatDuration(
                call.duration_seconds
              )}
            </span>

            <span
              className={
                `status `
                + `status-${
                  call.status
                }`
              }
            >
              {call.status}
            </span>
          </div>
        </header>

        {loading && (
          <p className="detail-state">
            Loading this call…
          </p>
        )}

        {error && (
          <div className="notice notice-error">
            <strong>
              Something went wrong.
            </strong>

            <p>
              {error}
            </p>
          </div>
        )}

        {!loading
          && !error
          && call.status
            !== "completed"
          && (
            <IncompleteCall
              call={call}

              onContinue={
                call.status
                  === "created"
                || (
                  call.status
                    === "failed"
                  && (
                    call
                      .failure_reason
                      === "recording_interrupted"
                    || call
                      .failure_reason
                      === "recording_start_failed"
                    || call
                      .failure_reason
                      === "recording_finish_failed"
                  )
                )
                  ? onContinueCreatedCall
                  : undefined
              }

              onProcess={
                call.status
                  === "processing"
                || (
                  call.status
                    === "failed"
                  && (
                    !call.failure_reason
                    || (
                      call
                        .failure_reason
                      === "processing_failed"
                    )
                  )
                )
                  ? onProcessCall
                  : undefined
              }
            />
          )}

        {!loading
          && !error
          && call.status
            === "completed"
          && notes
          && (
            <>
              <section className="recap-section">
                <h2>
                  Summary
                </h2>

                <p className="summary">
                  {notes.summary}
                </p>
              </section>

              <ListSection
                title="Key points"
                items={
                  notes.key_points
                }
              />

              <ListSection
                title="Decisions"
                items={
                  notes.decisions
                    .map(
                      (item) =>
                        item.decision
                    )
                }
              />

              <section className="recap-section">
                <h2>
                  Next steps
                </h2>

                <div className="next-steps">
                  <ActionColumn
                    title="My next steps"
                    items={tasks.filter(
                      (task) => task.owner === "me"
                    )}
                    loading={tasksLoading}
                    error={tasksError}
                    busyId={taskBusyId}
                    onUpdateTask={onUpdateTask}
                    onDeleteTask={onDeleteTask}
                  />

                  <ActionColumn
                    title="Their next steps"
                    items={tasks.filter(
                      (task) => task.owner === "them"
                    )}
                    loading={tasksLoading}
                    error={tasksError}
                    busyId={taskBusyId}
                    onUpdateTask={onUpdateTask}
                    onDeleteTask={onDeleteTask}
                  />
                </div>
              </section>

              {notes
                .important_dates
                .length > 0
                && (
                  <ListSection
                    title="Important dates"
                    items={
                      notes
                        .important_dates
                    }
                  />
                )}

              {notes.follow_up && (
                <section className="recap-section">
                  <h2>
                    Follow-up
                  </h2>

                  <p>
                    {notes.follow_up}
                  </p>
                </section>
              )}

              <section className="call-detail-ask">
                <div>
                  <span className="section-label">
                    Ask TCA
                  </span>

                  <h2>
                    Have a question about
                    this conversation?
                  </h2>
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={
                    onAskAboutCall
                  }
                >
                  Ask about this call
                </button>
              </section>

              <section className="transcript-section">
                <button
                  type="button"
                  className="transcript-toggle"
                  onClick={
                    onToggleTranscript
                  }
                >
                  <span>
                    Transcript
                  </span>

                  <span>
                    {transcriptOpen
                      ? "−"
                      : "+"}
                  </span>
                </button>

                {transcriptOpen
                  && transcript
                  && (
                    <pre className="transcript">
                      {transcript}
                    </pre>
                  )}
              </section>

              <footer className="recap-actions">
                <button
                  type="button"
                  className={
                    "action-button "
                    + "primary-action"
                  }
                  onClick={
                    onWhatsApp
                  }
                >
                  Share to WhatsApp
                </button>

                <button
                  type="button"
                  className="action-button"
                  onClick={
                    onCopy
                  }
                >
                  Copy
                </button>

                <button
                  type="button"
                  className="action-button"
                  onClick={
                    onDownload
                  }
                >
                  Download
                </button>
              </footer>

              {actionMessage && (
                <p className="system-message">
                  {actionMessage}
                </p>
              )}
            </>
          )}

        {canDelete && (
          <section className="recap-section">
            <button
              type="button"
              className="back-button"
              disabled={
                deleting
              }
              onClick={
                onDelete
              }
            >
              {deleting
                ? "Deleting…"
                : "Delete conversation"}
            </button>
          </section>
        )}
      </article>
    </main>
  );
}


function IncompleteCall({
  call,
  onContinue,
  onProcess,
}: {
  call: Call;

  onContinue?:
    () => void;

  onProcess?:
    () => void;
}) {
  if (
    call.status
      === "failed"
    && (
      call.failure_reason
      === "recording_interrupted"
    )
  ) {
    return (
      <div className="notice notice-error">
        <strong>
          Recording interrupted.
        </strong>

        <p>
          This recording session ended
          unexpectedly before it could
          be saved. You can start this
          call again.
        </p>

        {onContinue && (
          <button
            type="button"
            className="notice-action"
            onClick={
              onContinue
            }
          >
            Start again
          </button>
        )}
      </div>
    );
  }

  if (
    call.status
      === "failed"
    && (
      call.failure_reason
      === "recording_start_failed"
    )
  ) {
    return (
      <div className="notice notice-error">
        <strong>
          Recording couldn't start.
        </strong>

        <p>
          Check your audio devices
          and try again.
        </p>

        {onContinue && (
          <button
            type="button"
            className="notice-action"
            onClick={
              onContinue
            }
          >
            Try recording again
          </button>
        )}
      </div>
    );
  }

  if (
    call.status
      === "failed"
    && (
      call.failure_reason
      === "recording_finish_failed"
    )
  ) {
    return (
      <div className="notice notice-error">
        <strong>
          Recording didn't finish
          correctly.
        </strong>

        <p>
          The recording session could
          not be finalised. You can
          start the call again.
        </p>

        {onContinue && (
          <button
            type="button"
            className="notice-action"
            onClick={
              onContinue
            }
          >
            Start again
          </button>
        )}
      </div>
    );
  }

  if (
    call.status
      === "failed"
    && (
      call.failure_reason
      === "processing_failed"
    )
  ) {
    return (
      <div className="notice notice-error">
        <strong>
          Your recording is safe.
        </strong>

        <p>
          We couldn't prepare the notes.
          You can try processing the
          saved recording again.
        </p>

        {onProcess && (
          <button
            type="button"
            className="notice-action"
            onClick={
              onProcess
            }
          >
            Try processing again
          </button>
        )}
      </div>
    );
  }

  const copy:
  Record<
    Call["status"],
    {
      title:
        string;

      message:
        string;
    }
  > = {
    created: {
      title:
        "This call hasn't started yet.",

      message:
        "You can start recording "
        + "whenever you're ready.",
    },

    recording: {
      title:
        "This call is recording.",

      message:
        "Return to the active recording "
        + "session to finish it.",
    },

    paused: {
      title:
        "This call is paused.",

      message:
        "Resume the recording "
        + "when you're ready.",
    },

    processing: {
      title:
        "Your recording is ready.",

      message:
        "Process it to create the "
        + "transcript and call notes.",
    },

    completed: {
      title:
        "This call is complete.",

      message:
        "",
    },

    failed: {
      title:
        "This call didn't finish.",

      message:
        "You can try again.",
    },
  };

  const state =
    copy[
      call.status
    ];

  return (
    <div className="notice">
      <strong>
        {state.title}
      </strong>

      <p>
        {state.message}
      </p>

      {onContinue && (
        <button
          type="button"
          className="notice-action"
          onClick={
            onContinue
          }
        >
          Start this call
        </button>
      )}

      {onProcess && (
        <button
          type="button"
          className="notice-action"
          onClick={
            onProcess
          }
        >
          Prepare notes
        </button>
      )}
    </div>
  );
}


function ListSection({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  if (
    items.length === 0
  ) {
    return null;
  }

  return (
    <section className="recap-section">
      <h2>
        {title}
      </h2>

      <ul className="note-list">
        {items.map(
          (
            item,
            index
          ) => (
            <li
              key={
                index
              }
            >
              {item}
            </li>
          )
        )}
      </ul>
    </section>
  );
}


function ActionColumn({
  title,
  items,
  loading,
  error,
  busyId,
  onUpdateTask,
  onDeleteTask,
}: {
  title: string;
  items: Task[];
  loading: boolean;
  error: string;
  busyId: string | null;
  onUpdateTask: (
    taskId: string,
    changes: {
      task?: string;
      deadline?: string | null;
      completed?: boolean;
    }
  ) => Promise<void>;
  onDeleteTask: (
    taskId: string
  ) => Promise<void>;
}) {
  const [editingId, setEditingId] =
    useState<string | null>(null);

  const [draftTask, setDraftTask] =
    useState("");

  const [draftDeadline, setDraftDeadline] =
    useState("");

  function beginEdit(item: Task) {
    setEditingId(item.id);
    setDraftTask(item.task);
    setDraftDeadline(item.deadline || "");
  }

  function cancelEdit() {
    setEditingId(null);
    setDraftTask("");
    setDraftDeadline("");
  }

  async function saveEdit(item: Task) {
    const cleanTask = draftTask.trim();

    if (!cleanTask) {
      return;
    }

    try {
      await onUpdateTask(item.id, {
        task: cleanTask,
        deadline: draftDeadline.trim() || null,
      });
      cancelEdit();
    } catch {
      // Parent displays the error.
    }
  }

  async function toggleCompleted(item: Task) {
    try {
      await onUpdateTask(item.id, {
        completed: !item.completed,
      });
    } catch {
      // Parent displays the error.
    }
  }

  async function handleDelete(item: Task) {
    const confirmed = window.confirm(
      `Delete this next step?\n\n${item.task}`
    );

    if (!confirmed) {
      return;
    }

    try {
      await onDeleteTask(item.id);

      if (editingId === item.id) {
        cancelEdit();
      }
    } catch {
      // Parent displays the error.
    }
  }

  return (
    <div className="action-column">
      <h3>
        {title}
      </h3>

      {loading ? (
        <p className="muted">
          Loading next steps…
        </p>
      ) : items.length === 0 ? (
        <p className="muted">
          Nothing assigned.
        </p>
      ) : (
        <ul className="task-list">
          {items.map((item) => {
            const busy = busyId === item.id;
            const editing = editingId === item.id;

            return (
              <li
                className={
                  `task-item${
                    item.completed
                      ? " task-completed"
                      : ""
                  }`
                }
                key={item.id}
              >
                {editing ? (
                  <div className="task-edit-form">
                    <label>
                      <span>Task</span>
                      <input
                        value={draftTask}
                        onChange={(event) =>
                          setDraftTask(event.target.value)
                        }
                        maxLength={500}
                        disabled={busy}
                      />
                    </label>

                    <label>
                      <span>Deadline</span>
                      <input
                        value={draftDeadline}
                        onChange={(event) =>
                          setDraftDeadline(event.target.value)
                        }
                        maxLength={200}
                        placeholder="Optional"
                        disabled={busy}
                      />
                    </label>

                    <div className="task-edit-actions">
                      <button
                        type="button"
                        className="task-text-button"
                        onClick={() => saveEdit(item)}
                        disabled={busy || !draftTask.trim()}
                      >
                        {busy ? "Saving…" : "Save"}
                      </button>

                      <button
                        type="button"
                        className="task-text-button"
                        onClick={cancelEdit}
                        disabled={busy}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      className="task-check"
                      aria-label={
                        item.completed
                          ? "Reopen task"
                          : "Complete task"
                      }
                      aria-pressed={item.completed}
                      onClick={() => toggleCompleted(item)}
                      disabled={busy}
                    >
                      <span aria-hidden="true">
                        {item.completed ? "✓" : ""}
                      </span>
                    </button>

                    <div className="task-content">
                      <span className="task-text">
                        {item.task}
                      </span>

                      {item.deadline && (
                        <small>
                          {item.deadline}
                        </small>
                      )}

                      {item.completed && (
                        <span className="task-completed-label">
                          Completed
                        </span>
                      )}
                    </div>

                    <div className="task-actions">
                      <button
                        type="button"
                        className="task-icon-button"
                        onClick={() => beginEdit(item)}
                        disabled={busy}
                        aria-label="Edit task"
                        title="Edit task"
                      >
                        Edit
                      </button>

                      <button
                        type="button"
                        className="task-icon-button task-delete-button"
                        onClick={() => handleDelete(item)}
                        disabled={busy}
                        aria-label="Delete task"
                        title="Delete task"
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {error && items.length > 0 && (
        <p className="task-error">
          {error}
        </p>
      )}
    </div>
  );
}


function TopBar({
  theme,
  onToggleTheme,
}: {
  theme: Theme;

  onToggleTheme:
    () => void;
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">
          TCA
        </span>

        <span className="brand-name">
          The Call Assistant
        </span>
      </div>

      <div className="topbar-actions">
        <button
          className="theme-toggle"
          type="button"
          onClick={
            onToggleTheme
          }
          aria-label={
            theme === "dark"
              ? (
                "Switch to "
                + "light mode"
              )
              : (
                "Switch to "
                + "dark mode"
              )
          }
          title={
            theme === "dark"
              ? "Light mode"
              : "Dark mode"
          }
        >
          {theme === "dark"
            ? "☀"
            : "☾"}
        </button>

        <span className="version">
          V0.3
        </span>
      </div>
    </header>
  );
}


export default App;