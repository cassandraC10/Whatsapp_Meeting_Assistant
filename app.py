import os
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import filedialog
from urllib.parse import quote

import customtkinter as ctk

from audio.recorder import MeetingRecorder
from intelligence.summarizer import summarize_meeting
from storage.meeting_store import MeetingStore
from transcription.transcriber import transcribe_meeting
from whatsapp.formatter import format_for_whatsapp


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ConversationAssistantApp(ctk.CTk):

    ACCENT = "#8B7CF6"
    ACCENT_HOVER = "#7567DB"
    SUCCESS = "#58D68D"
    WARNING = "#F4C95D"
    ERROR = "#FF6B6B"

    MUTED = "#A0A0A0"

    CARD = "#292929"
    INNER_CARD = "#202020"

    def __init__(self):
        super().__init__()

        self.title("Conversation Assistant")
        self.geometry("1120x820")
        self.minsize(950, 720)

        self.recorder = None
        self.meeting_store = MeetingStore()

        self.recording = False
        self.start_time = None

        self.current_meeting_name = None
        self.current_whatsapp_text = None
        self.current_text_notes = None
        self.current_meeting_directory = None
        self.current_recording_duration = None

        self.current_notes = None

        self.audio_saved = False
        self.last_processing_error = None

        self._configure_window()
        self._build_header()
        self._build_recording_card()
        self._build_results_area()

    # ========================================================
    # WINDOW
    # ========================================================

    def _configure_window(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

    # ========================================================
    # HEADER
    # ========================================================

    def _build_header(self):
        header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=46,
            pady=(30, 18)
        )

        header.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkLabel(
            header,
            text="CONVERSATION ASSISTANT",
            font=ctk.CTkFont(
                size=12,
                weight="bold"
            ),
            text_color=self.ACCENT
        )

        brand.grid(
            row=0,
            column=0,
            sticky="w"
        )

        title = ctk.CTkLabel(
            header,
            text="Keep track of what matters in every call.",
            font=ctk.CTkFont(
                size=31,
                weight="bold"
            )
        )

        title.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(6, 3)
        )

        subtitle = ctk.CTkLabel(
            header,
            text=(
                "Stay focused on the conversation. "
                "Your notes, next steps and important dates will be ready when you're done."
            ),
            font=ctk.CTkFont(size=14),
            text_color=self.MUTED
        )

        subtitle.grid(
            row=2,
            column=0,
            sticky="w"
        )

    # ========================================================
    # RECORDING CARD
    # ========================================================

    def _build_recording_card(self):
        self.recording_card = ctk.CTkFrame(
            self,
            corner_radius=18,
            fg_color=self.CARD
        )

        self.recording_card.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=46,
            pady=(0, 18)
        )

        self.recording_card.grid_columnconfigure(0, weight=1)

        self.meeting_name_entry = ctk.CTkEntry(
            self.recording_card,
            placeholder_text="What is this call about?",
            height=48,
            corner_radius=12,
            border_width=1
        )

        self.meeting_name_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=26,
            pady=(24, 16)
        )

        info_frame = ctk.CTkFrame(
            self.recording_card,
            fg_color="transparent"
        )

        info_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=28
        )

        info_frame.grid_columnconfigure(1, weight=1)

        self.status_label = ctk.CTkLabel(
            info_frame,
            text="● Ready",
            font=ctk.CTkFont(
                size=16,
                weight="bold"
            ),
            text_color=self.ACCENT
        )

        self.status_label.grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.timer_label = ctk.CTkLabel(
            info_frame,
            text="00:00",
            font=ctk.CTkFont(
                size=39,
                weight="bold"
            )
        )

        self.timer_label.grid(
            row=0,
            column=1
        )

        headphone_label = ctk.CTkLabel(
            info_frame,
            text="🎧 Headphones give the cleanest results",
            font=ctk.CTkFont(size=12),
            text_color=self.MUTED
        )

        headphone_label.grid(
            row=0,
            column=2,
            sticky="e"
        )

        buttons = ctk.CTkFrame(
            self.recording_card,
            fg_color="transparent"
        )

        buttons.grid(
            row=2,
            column=0,
            pady=(18, 10)
        )

        self.start_button = ctk.CTkButton(
            buttons,
            text="Start call notes",
            width=190,
            height=46,
            corner_radius=12,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT_HOVER,
            command=self.start_meeting
        )

        self.start_button.grid(
            row=0,
            column=0,
            padx=7
        )

        self.stop_button = ctk.CTkButton(
            buttons,
            text="Finish & get notes",
            width=190,
            height=46,
            corner_radius=12,
            command=self.stop_meeting,
            state="disabled"
        )

        self.stop_button.grid(
            row=0,
            column=1,
            padx=7
        )

        self.processing_label = ctk.CTkLabel(
            self.recording_card,
            text="Ready when you are.",
            font=ctk.CTkFont(size=13),
            text_color=self.MUTED
        )

        self.processing_label.grid(
            row=3,
            column=0,
            pady=(4, 22)
        )

    # ========================================================
    # RESULTS AREA
    # ========================================================

    def _build_results_area(self):
        self.results_card = ctk.CTkFrame(
            self,
            corner_radius=18,
            fg_color=self.CARD
        )

        self.results_card.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=46,
            pady=(0, 28)
        )

        self.results_card.grid_columnconfigure(0, weight=1)
        self.results_card.grid_rowconfigure(1, weight=1)

        heading_frame = ctk.CTkFrame(
            self.results_card,
            fg_color="transparent"
        )

        heading_frame.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=26,
            pady=(20, 8)
        )

        heading_frame.grid_columnconfigure(0, weight=1)

        self.results_heading = ctk.CTkLabel(
            heading_frame,
            text="After the call",
            font=ctk.CTkFont(
                size=17,
                weight="bold"
            )
        )

        self.results_heading.grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.results_subtitle = ctk.CTkLabel(
            heading_frame,
            text="Your notes will show up here.",
            font=ctk.CTkFont(size=12),
            text_color=self.MUTED
        )

        self.results_subtitle.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(2, 0)
        )

        self.notes_scroll = ctk.CTkScrollableFrame(
            self.results_card,
            corner_radius=12,
            fg_color=self.INNER_CARD
        )

        self.notes_scroll.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=26,
            pady=(8, 16)
        )

        self.notes_scroll.grid_columnconfigure(0, weight=1)

        self._show_empty_state()

        self.action_frame = ctk.CTkFrame(
            self.results_card,
            fg_color="transparent"
        )

        self.action_frame.grid(
            row=2,
            column=0,
            pady=(0, 20)
        )

        self.transcript_button = ctk.CTkButton(
            self.action_frame,
            text="Transcript",
            width=125,
            command=self.show_transcript,
            state="disabled"
        )

        self.transcript_button.grid(
            row=0,
            column=0,
            padx=5
        )

        self.download_button = ctk.CTkButton(
            self.action_frame,
            text="Download notes",
            width=145,
            command=self.download_notes,
            state="disabled"
        )

        self.download_button.grid(
            row=0,
            column=1,
            padx=5
        )

        self.whatsapp_button = ctk.CTkButton(
            self.action_frame,
            text="Send to WhatsApp",
            width=150,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT_HOVER,
            command=self.send_to_whatsapp,
            state="disabled"
        )

        self.whatsapp_button.grid(
            row=0,
            column=2,
            padx=5
        )

        self.folder_button = ctk.CTkButton(
            self.action_frame,
            text="Open files",
            width=120,
            command=self.open_meeting_folder,
            state="disabled"
        )

        self.folder_button.grid(
            row=0,
            column=3,
            padx=5
        )

        self.retry_button = ctk.CTkButton(
            self.results_card,
            text="Try again",
            width=140,
            fg_color=self.WARNING,
            text_color="#111111",
            command=self.retry_processing,
            state="disabled"
        )

        self.retry_button.grid(
            row=3,
            column=0,
            pady=(0, 18)
        )

    # ========================================================
    # EMPTY RESULTS
    # ========================================================

    def _clear_notes_area(self):
        for widget in self.notes_scroll.winfo_children():
            widget.destroy()

    def _show_empty_state(self):
        self._clear_notes_area()

        empty = ctk.CTkLabel(
            self.notes_scroll,
            text=(
                "Nothing to review yet.\n\n"
                "Start a call and your notes will appear here when you're finished."
            ),
            justify="center",
            font=ctk.CTkFont(size=14),
            text_color=self.MUTED
        )

        empty.grid(
            row=0,
            column=0,
            padx=30,
            pady=70
        )

    # ========================================================
    # START
    # ========================================================

    def start_meeting(self):
        meeting_name = self.meeting_name_entry.get().strip()

        if not meeting_name:
            self.set_status(
                "Give this call a name first."
            )
            return

        try:
            self.recorder = MeetingRecorder()
            self.recorder.start()

        except Exception as error:
            self.set_status(
                f"Couldn't start the recording: {error}"
            )
            return

        self.current_meeting_name = meeting_name
        self.current_whatsapp_text = None
        self.current_text_notes = None
        self.current_meeting_directory = None
        self.current_recording_duration = None
        self.current_notes = None

        self.audio_saved = False
        self.last_processing_error = None

        self.recording = True
        self.start_time = time.time()

        self.status_label.configure(
            text="● Listening",
            text_color=self.ERROR
        )

        self.processing_label.configure(
            text="Stay focused on your call — we've got the notes."
        )

        self.start_button.configure(
            state="disabled"
        )

        self.stop_button.configure(
            state="normal"
        )

        self.meeting_name_entry.configure(
            state="disabled"
        )

        self.retry_button.configure(
            state="disabled"
        )

        self.disable_output_buttons()

        self.results_heading.configure(
            text="Call in progress"
        )

        self.results_subtitle.configure(
            text="Your notes will be ready when you finish."
        )

        self._clear_notes_area()

        recording_message = ctk.CTkLabel(
            self.notes_scroll,
            text=(
                "Listening to the conversation…\n\n"
                "You can keep your attention on the call."
            ),
            justify="center",
            font=ctk.CTkFont(size=15),
            text_color=self.MUTED
        )

        recording_message.grid(
            row=0,
            column=0,
            pady=70
        )

        self.update_timer()

    # ========================================================
    # TIMER
    # ========================================================

    def update_timer(self):
        if not self.recording:
            return

        elapsed = int(
            time.time() - self.start_time
        )

        minutes = elapsed // 60
        seconds = elapsed % 60

        self.timer_label.configure(
            text=f"{minutes:02d}:{seconds:02d}"
        )

        self.after(
            1000,
            self.update_timer
        )

    # ========================================================
    # STOP
    # ========================================================

    def stop_meeting(self):
        if not self.recording:
            return

        self.recording = False

        self.stop_button.configure(
            state="disabled"
        )

        self.status_label.configure(
            text="● Working on your notes",
            text_color=self.WARNING
        )

        self.processing_label.configure(
            text="Saving your call…"
        )

        self.results_heading.configure(
            text="Getting your notes ready"
        )

        self.results_subtitle.configure(
            text="This normally takes a moment."
        )

        worker = threading.Thread(
            target=self.process_meeting,
            kwargs={"retry_only": False},
            daemon=True
        )

        worker.start()

    # ========================================================
    # PROCESSING
    # ========================================================

    def process_meeting(self, retry_only=False):
        try:
            if not retry_only:
                self.update_processing(
                    "Saving your call…"
                )

                recording_result = self.recorder.stop()

                self.current_recording_duration = (
                    recording_result["duration"]
                )

                self.audio_saved = True

            self.update_processing(
                "Turning the conversation into notes…"
            )

            transcribe_meeting(
                status_callback=self.update_processing
            )

            self.update_processing(
                "Pulling out the important parts…"
            )

            notes, text_notes = summarize_meeting(
                status_callback=self.update_processing
            )

            self.current_notes = notes
            self.current_text_notes = text_notes

            self.update_processing(
                "Getting everything ready to share…"
            )

            whatsapp_text = format_for_whatsapp(
                notes
            )

            self.current_whatsapp_text = whatsapp_text

            self.update_processing(
                "Saving this call…"
            )

            meeting_directory = self.meeting_store.save_meeting(
                meeting_name=self.current_meeting_name,
                whatsapp_text=whatsapp_text,
                duration=self.current_recording_duration
            )

            self.current_meeting_directory = meeting_directory

            self.after(
                0,
                lambda: self.display_notes(notes)
            )

        except Exception as error:
            self.last_processing_error = error

            self.after(
                0,
                lambda err=error: self.processing_failed(err)
            )

    # ========================================================
    # RESULTS
    # ========================================================

    def display_notes(self, notes):
        self.status_label.configure(
            text="✓ Done",
            text_color=self.SUCCESS
        )

        self.processing_label.configure(
            text="Your call is saved and your notes are ready."
        )

        self.results_heading.configure(
            text=self.current_meeting_name
        )

        self.results_subtitle.configure(
            text="Here's what came out of the conversation."
        )

        self._clear_notes_area()

        row = 0

        self._add_section(
            row,
            "What you talked about",
            notes.summary
        )

        row += 1

        self._add_list_section(
            row,
            "Key points",
            notes.key_points
        )

        row += 1

        my_tasks = [
            self._format_task(item)
            for item in notes.my_action_items
        ]

        their_tasks = [
            self._format_task(item)
            for item in notes.client_action_items
        ]

        actions_frame = ctk.CTkFrame(
            self.notes_scroll,
            fg_color="transparent"
        )

        actions_frame.grid(
            row=row,
            column=0,
            sticky="ew",
            padx=4,
            pady=5
        )

        actions_frame.grid_columnconfigure(
            (0, 1),
            weight=1
        )

        self._add_small_card(
            actions_frame,
            0,
            "My next steps",
            my_tasks
        )

        self._add_small_card(
            actions_frame,
            1,
            "Their next steps",
            their_tasks
        )

        row += 1

        decisions = [
            item.decision
            for item in notes.decisions
        ]

        self._add_list_section(
            row,
            "What was decided",
            decisions
        )

        row += 1

        self._add_list_section(
            row,
            "Important dates",
            notes.deadlines
        )

        row += 1

        self._add_section(
            row,
            "Follow-up",
            notes.follow_up or "Nothing scheduled yet."
        )

        self.enable_output_buttons()

        self.retry_button.configure(
            state="disabled"
        )

        self.start_button.configure(
            state="normal"
        )

        self.meeting_name_entry.configure(
            state="normal"
        )

    # ========================================================
    # NOTE CARDS
    # ========================================================

    def _add_section(
        self,
        row,
        title,
        content
    ):
        card = ctk.CTkFrame(
            self.notes_scroll,
            corner_radius=12,
            fg_color=self.CARD
        )

        card.grid(
            row=row,
            column=0,
            sticky="ew",
            padx=5,
            pady=6
        )

        card.grid_columnconfigure(
            0,
            weight=1
        )

        heading = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(
                size=14,
                weight="bold"
            )
        )

        heading.grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=(15, 5)
        )

        body = ctk.CTkLabel(
            card,
            text=content or "Nothing noted.",
            font=ctk.CTkFont(size=13),
            text_color="#D8D8D8",
            justify="left",
            anchor="w",
            wraplength=900
        )

        body.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 16)
        )

    def _add_list_section(
        self,
        row,
        title,
        items
    ):
        text = (
            "\n".join(
                f"• {item}"
                for item in items
            )
            if items
            else "Nothing noted."
        )

        self._add_section(
            row,
            title,
            text
        )

    def _add_small_card(
        self,
        parent,
        column,
        title,
        items
    ):
        card = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=self.CARD
        )

        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=5
        )

        heading = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(
                size=14,
                weight="bold"
            )
        )

        heading.pack(
            anchor="w",
            padx=18,
            pady=(15, 7)
        )

        content = (
            "\n\n".join(
                f"• {item}"
                for item in items
            )
            if items
            else "Nothing for now."
        )

        body = ctk.CTkLabel(
            card,
            text=content,
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=13),
            text_color="#D8D8D8",
            wraplength=400
        )

        body.pack(
            anchor="w",
            padx=18,
            pady=(0, 16)
        )

    def _format_task(self, item):
        if item.deadline:
            return (
                f"{item.task}\n"
                f"Due: {item.deadline}"
            )

        return item.task

    # ========================================================
    # FAILURE
    # ========================================================

    def processing_failed(self, error):
        print(
            "Processing error:",
            error
        )

        if self.audio_saved:
            self.status_label.configure(
                text="⚠ Couldn't finish",
                text_color=self.WARNING
            )

            self.processing_label.configure(
                text=(
                    "Your call is safe. "
                    "You can try again when you're ready."
                )
            )

            self.results_heading.configure(
                text="Your recording is safe"
            )

            self.results_subtitle.configure(
                text=(
                    "We couldn't finish the notes this time. "
                    "Nothing needs to be recorded again."
                )
            )

            self.retry_button.configure(
                state="normal"
            )

            self.start_button.configure(
                state="disabled"
            )

            return

        self.status_label.configure(
            text="✕ Something went wrong",
            text_color=self.ERROR
        )

        self.processing_label.configure(
            text=str(error)
        )

        self.start_button.configure(
            state="normal"
        )

        self.meeting_name_entry.configure(
            state="normal"
        )

    # ========================================================
    # RETRY
    # ========================================================

    def retry_processing(self):
        if not self.audio_saved:
            return

        self.retry_button.configure(
            state="disabled"
        )

        self.status_label.configure(
            text="● Trying again",
            text_color=self.WARNING
        )

        self.processing_label.configure(
            text="Picking up from your saved recording…"
        )

        worker = threading.Thread(
            target=self.process_meeting,
            kwargs={"retry_only": True},
            daemon=True
        )

        worker.start()

    # ========================================================
    # STATUS
    # ========================================================

    def update_processing(self, message):
        self.after(
            0,
            lambda: self.processing_label.configure(
                text=message
            )
        )

    def set_status(self, message):
        self.processing_label.configure(
            text=message
        )

    # ========================================================
    # TRANSCRIPT
    # ========================================================

    def show_transcript(self):
        try:
            transcript = Path(
                "combined_transcript.txt"
            ).read_text(
                encoding="utf-8"
            )

        except FileNotFoundError:
            self.set_status(
                "Couldn't find the transcript."
            )
            return

        window = ctk.CTkToplevel(self)

        window.title("Conversation transcript")
        window.geometry("780x650")

        heading = ctk.CTkLabel(
            window,
            text="Conversation transcript",
            font=ctk.CTkFont(
                size=22,
                weight="bold"
            )
        )

        heading.pack(
            anchor="w",
            padx=28,
            pady=(24, 12)
        )

        textbox = ctk.CTkTextbox(
            window,
            wrap="word",
            corner_radius=12
        )

        textbox.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=(0, 28)
        )

        textbox.insert(
            "1.0",
            transcript
        )

        textbox.configure(
            state="disabled"
        )

    # ========================================================
    # DOWNLOAD
    # ========================================================

    def download_notes(self):
        if not self.current_text_notes:
            return

        name = (
            self.current_meeting_name
            or "conversation"
        )

        name = name.replace(
            " ",
            "_"
        )

        path = filedialog.asksaveasfilename(
            title="Save notes",
            defaultextension=".txt",
            filetypes=[
                ("Text document", "*.txt")
            ],
            initialfile=f"{name}_notes.txt"
        )

        if not path:
            return

        Path(path).write_text(
            self.current_text_notes,
            encoding="utf-8"
        )

        self.set_status(
            "Notes saved."
        )

    # ========================================================
    # WHATSAPP
    # ========================================================

    def send_to_whatsapp(self):
        if not self.current_whatsapp_text:
            return

        message = quote(
            self.current_whatsapp_text
        )

        webbrowser.open(
            f"https://wa.me/?text={message}"
        )

        self.set_status(
            "WhatsApp is ready with your notes."
        )

    # ========================================================
    # OPEN FILES
    # ========================================================

    def open_meeting_folder(self):
        if not self.current_meeting_directory:
            return

        try:
            os.startfile(
                self.current_meeting_directory
            )

        except Exception as error:
            self.set_status(
                f"Couldn't open the folder: {error}"
            )

    # ========================================================
    # BUTTON HELPERS
    # ========================================================

    def enable_output_buttons(self):
        for button in (
            self.transcript_button,
            self.download_button,
            self.whatsapp_button,
            self.folder_button,
        ):
            button.configure(
                state="normal"
            )

    def disable_output_buttons(self):
        for button in (
            self.transcript_button,
            self.download_button,
            self.whatsapp_button,
            self.folder_button,
        ):
            button.configure(
                state="disabled"
            )


if __name__ == "__main__":
    app = ConversationAssistantApp()
    app.mainloop()