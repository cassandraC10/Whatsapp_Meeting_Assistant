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

# ============================================================
# APP THEME
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ============================================================
# APPLICATION
# ============================================================

class MeetingAssistantApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # ====================================================
        # WINDOW
        # ====================================================

        self.title("WhatsApp Meeting Assistant")
        self.geometry("1050x780")
        self.minsize(900, 680)

        # ====================================================
        # APPLICATION STATE
        # ====================================================

        self.recorder = None
        self.meeting_store = MeetingStore()

        self.recording = False
        self.start_time = None

        self.current_meeting_name = None
        self.current_whatsapp_text = None
        self.current_text_notes = None
        self.current_meeting_directory = None
        self.current_recording_duration = None

        # True after recorder.stop() succeeds.
        #
        # This allows us to retry Gemini/network processing
        # without trying to stop the recorder twice.
        self.audio_saved = False

        self.last_processing_error = None

        # ====================================================
        # ROOT GRID
        # ====================================================

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ====================================================
        # HEADER
        # ====================================================

        self.header = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=40,
            pady=(28, 15),
        )

        self.header.grid_columnconfigure(0, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.header,
            text="CHAT MEETING ASSISTANT",
            font=ctk.CTkFont(
                size=13,
                weight="bold",
            ),
            text_color="#B8A7FF",
        )

        self.logo_label.grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.title_label = ctk.CTkLabel(
            self.header,
            text="Know what was said, and what happens next.",
            font=ctk.CTkFont(
                size=30,
                weight="bold",
            ),
        )

        self.title_label.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(5, 0),
        )

        self.subtitle_label = ctk.CTkLabel(
            self.header,
            text=(
                "Record your WhatsApp meeting, identify both speakers, "
                "and generate structured meeting notes."
            ),
            font=ctk.CTkFont(size=14),
            text_color="#A5A5A5",
        )

        self.subtitle_label.grid(
            row=2,
            column=0,
            sticky="w",
            pady=(5, 0),
        )

        # ====================================================
        # CONTROL CARD
        # ====================================================

        self.control_card = ctk.CTkFrame(
            self,
            corner_radius=18,
        )

        self.control_card.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=40,
            pady=(0, 18),
        )

        self.control_card.grid_columnconfigure(
            0,
            weight=1,
        )

        # ----------------------------------------------------
        # Meeting name
        # ----------------------------------------------------

        self.meeting_name_entry = ctk.CTkEntry(
            self.control_card,
            placeholder_text="Meeting name e.g. Project Timeline Review",
            height=48,
            corner_radius=12,
        )

        self.meeting_name_entry.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=25,
            pady=(25, 15),
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.status_label = ctk.CTkLabel(
            self.control_card,
            text="● READY",
            font=ctk.CTkFont(
                size=16,
                weight="bold",
            ),
            text_color="#B8A7FF",
        )

        self.status_label.grid(
            row=1,
            column=0,
            sticky="w",
            padx=(25, 10),
            pady=10,
        )

        # ----------------------------------------------------
        # Timer
        # ----------------------------------------------------

        self.timer_label = ctk.CTkLabel(
            self.control_card,
            text="00:00",
            font=ctk.CTkFont(
                size=38,
                weight="bold",
            ),
        )

        self.timer_label.grid(
            row=1,
            column=1,
            padx=20,
            pady=10,
        )

        # ----------------------------------------------------
        # Headphones reminder
        # ----------------------------------------------------

        self.headphones_label = ctk.CTkLabel(
            self.control_card,
            text="🎧 Headphones recommended",
            font=ctk.CTkFont(size=12),
            text_color="#999999",
        )

        self.headphones_label.grid(
            row=1,
            column=2,
            sticky="e",
            padx=(10, 25),
        )

        # ----------------------------------------------------
        # Recording buttons
        # ----------------------------------------------------

        self.recording_buttons = ctk.CTkFrame(
            self.control_card,
            fg_color="transparent",
        )

        self.recording_buttons.grid(
            row=2,
            column=0,
            columnspan=3,
            pady=(8, 15),
        )

        self.start_button = ctk.CTkButton(
            self.recording_buttons,
            text="▶  START MEETING",
            width=190,
            height=46,
            corner_radius=12,
            command=self.start_meeting,
        )

        self.start_button.grid(
            row=0,
            column=0,
            padx=8,
        )

        self.stop_button = ctk.CTkButton(
            self.recording_buttons,
            text="■  STOP & SUMMARIZE",
            width=210,
            height=46,
            corner_radius=12,
            command=self.stop_meeting,
            state="disabled",
        )

        self.stop_button.grid(
            row=0,
            column=1,
            padx=8,
        )

        # ----------------------------------------------------
        # Processing stage
        # ----------------------------------------------------

        self.processing_label = ctk.CTkLabel(
            self.control_card,
            text="Ready for a meeting.",
            font=ctk.CTkFont(size=13),
            text_color="#AAAAAA",
        )

        self.processing_label.grid(
            row=3,
            column=0,
            columnspan=3,
            pady=(5, 22),
        )

        # ====================================================
        # NOTES AREA
        # ====================================================

        self.notes_card = ctk.CTkFrame(
            self,
            corner_radius=18,
        )

        self.notes_card.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=40,
            pady=(0, 20),
        )

        self.notes_card.grid_columnconfigure(
            0,
            weight=1,
        )

        self.notes_card.grid_rowconfigure(
            1,
            weight=1,
        )

        self.notes_header = ctk.CTkLabel(
            self.notes_card,
            text="MEETING NOTES",
            font=ctk.CTkFont(
                size=15,
                weight="bold",
            ),
        )

        self.notes_header.grid(
            row=0,
            column=0,
            sticky="w",
            padx=25,
            pady=(20, 8),
        )

        self.notes_box = ctk.CTkTextbox(
            self.notes_card,
            wrap="word",
            corner_radius=12,
            font=ctk.CTkFont(size=14),
        )

        self.notes_box.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=25,
            pady=(0, 18),
        )

        self.notes_box.insert(
            "1.0",
            (
                "Your meeting summary, decisions, deadlines "
                "and action items will appear here."
            ),
        )

        self.notes_box.configure(
            state="disabled"
        )

        # ====================================================
        # OUTPUT ACTIONS
        # ====================================================

        self.output_frame = ctk.CTkFrame(
            self.notes_card,
            fg_color="transparent",
        )

        self.output_frame.grid(
            row=2,
            column=0,
            pady=(0, 22),
        )

        self.transcript_button = ctk.CTkButton(
            self.output_frame,
            text="VIEW TRANSCRIPT",
            width=155,
            command=self.show_transcript,
            state="disabled",
        )

        self.transcript_button.grid(
            row=0,
            column=0,
            padx=5,
        )

        self.download_button = ctk.CTkButton(
            self.output_frame,
            text="DOWNLOAD NOTES",
            width=155,
            command=self.download_notes,
            state="disabled",
        )

        self.download_button.grid(
            row=0,
            column=1,
            padx=5,
        )

        self.whatsapp_button = ctk.CTkButton(
            self.output_frame,
            text="SEND TO WHATSAPP",
            width=165,
            command=self.send_to_whatsapp,
            state="disabled",
        )

        self.whatsapp_button.grid(
            row=0,
            column=2,
            padx=5,
        )

        self.folder_button = ctk.CTkButton(
            self.output_frame,
            text="OPEN SAVED MEETING",
            width=175,
            command=self.open_meeting_folder,
            state="disabled",
        )

        self.folder_button.grid(
            row=0,
            column=3,
            padx=5,
        )

        # ====================================================
        # RETRY BUTTON
        # ====================================================

        self.retry_button = ctk.CTkButton(
            self.notes_card,
            text="↻  RETRY PROCESSING",
            width=200,
            command=self.retry_processing,
            state="disabled",
        )

        self.retry_button.grid(
            row=3,
            column=0,
            pady=(0, 20),
        )

    # ========================================================
    # START MEETING
    # ========================================================

    def start_meeting(self):

        meeting_name = (
            self.meeting_name_entry
            .get()
            .strip()
        )

        if not meeting_name:

            self.set_status(
                "Please enter a meeting name."
            )

            return

        try:

            self.recorder = MeetingRecorder()
            self.recorder.start()

        except Exception as error:

            self.set_status(
                f"Recording error: {error}"
            )

            return

        # ----------------------------------------------------
        # Reset meeting state
        # ----------------------------------------------------

        self.current_meeting_name = meeting_name
        self.current_whatsapp_text = None
        self.current_text_notes = None
        self.current_meeting_directory = None
        self.current_recording_duration = None

        self.audio_saved = False
        self.last_processing_error = None

        self.recording = True
        self.start_time = time.time()

        # ----------------------------------------------------
        # UI
        # ----------------------------------------------------

        self.status_label.configure(
            text="● RECORDING",
            text_color="#FF6B6B",
        )

        self.processing_label.configure(
            text="Recording microphone + WhatsApp audio..."
        )

        self.start_button.configure(
            state="disabled"
        )

        self.stop_button.configure(
            state="normal"
        )

        self.retry_button.configure(
            state="disabled"
        )

        self.disable_output_buttons()

        self.meeting_name_entry.configure(
            state="disabled"
        )

        self.notes_box.configure(
            state="normal"
        )

        self.notes_box.delete(
            "1.0",
            "end",
        )

        self.notes_box.insert(
            "1.0",
            (
                "Recording in progress...\n\n"
                "Your meeting notes will appear here "
                "after processing."
            ),
        )

        self.notes_box.configure(
            state="disabled"
        )

        self.update_timer()

    # ========================================================
    # TIMER
    # ========================================================

    def update_timer(self):

        if not self.recording:
            return

        elapsed = int(
            time.time()
            - self.start_time
        )

        minutes = elapsed // 60
        seconds = elapsed % 60

        self.timer_label.configure(
            text=f"{minutes:02d}:{seconds:02d}"
        )

        self.after(
            1000,
            self.update_timer,
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
            text="● PROCESSING",
            text_color="#F4C95D",
        )

        self.processing_label.configure(
            text="Saving recording..."
        )

        worker = threading.Thread(
            target=self.process_meeting,
            kwargs={
                "retry_only": False
            },
            daemon=True,
        )

        worker.start()

    # ========================================================
    # PROCESS MEETING
    # ========================================================

    def process_meeting(
        self,
        retry_only=False,
    ):

        try:

            # =================================================
            # AUDIO
            # =================================================

            if not retry_only:

                self.update_processing(
                    "Step 1/5 — Saving recording..."
                )

                recording_result = (
                    self.recorder.stop()
                )

                self.current_recording_duration = (
                    recording_result[
                        "duration"
                    ]
                )

                self.audio_saved = True

            # =================================================
            # TRANSCRIPTION
            # =================================================

            self.update_processing(
                "Step 2/5 — Transcribing speakers..."
            )

            transcribe_meeting(
                status_callback=(
                    self.update_processing
                )
            )

            # =================================================
            # AI NOTES
            # =================================================

            self.update_processing(
                "Step 3/5 — Generating meeting notes..."
            )

            notes, text_notes = (
                summarize_meeting(
                    status_callback=(
                        self.update_processing
                    )
                )
            )

            self.current_text_notes = (
                text_notes
            )

            # =================================================
            # WHATSAPP FORMAT
            # =================================================

            self.update_processing(
                "Step 4/5 — Preparing WhatsApp summary..."
            )

            whatsapp_text = (
                format_for_whatsapp(
                    notes
                )
            )

            self.current_whatsapp_text = (
                whatsapp_text
            )

            # =================================================
            # STORAGE
            # =================================================

            self.update_processing(
                "Step 5/5 — Saving meeting history..."
            )

            meeting_directory = (
                self.meeting_store.save_meeting(
                    meeting_name=(
                        self.current_meeting_name
                    ),
                    whatsapp_text=(
                        whatsapp_text
                    ),
                    duration=(
                        self.current_recording_duration
                    ),
                )
            )

            self.current_meeting_directory = (
                meeting_directory
            )

            # =================================================
            # COMPLETE
            # =================================================

            self.after(
                0,
                lambda: self.display_notes(
                    text_notes
                ),
            )

        except Exception as error:

            self.last_processing_error = (
                error
            )

            self.after(
                0,
                lambda err=error:
                self.processing_failed(
                    err
                ),
            )

    # ========================================================
    # NETWORK ERROR CHECK
    # ========================================================

    def is_network_error(
        self,
        error,
    ):

        message = str(
            error
        ).lower()

        indicators = [
            "connection",
            "network",
            "internet",
            "timeout",
            "timed out",
            "dns",
            "name resolution",
            "getaddrinfo",
            "503",
            "unavailable",
            "429",
            "resource exhausted",
            "high demand",
        ]

        return any(
            word in message
            for word in indicators
        )

    # ========================================================
    # RETRY PROCESSING
    # ========================================================

    def retry_processing(self):

        if not self.audio_saved:

            self.set_status(
                "No saved recording is available to retry."
            )

            return

        self.retry_button.configure(
            state="disabled"
        )

        self.start_button.configure(
            state="disabled"
        )

        self.status_label.configure(
            text="● RETRYING",
            text_color="#F4C95D",
        )

        self.processing_label.configure(
            text="Retrying saved meeting..."
        )

        worker = threading.Thread(
            target=self.process_meeting,
            kwargs={
                "retry_only": True
            },
            daemon=True,
        )

        worker.start()

    # ========================================================
    # THREAD SAFE STATUS
    # ========================================================

    def update_processing(
        self,
        message,
    ):

        self.after(
            0,
            lambda: (
                self.processing_label
                .configure(
                    text=message
                )
            ),
        )

    # ========================================================
    # COMPLETE
    # ========================================================

    def display_notes(
        self,
        text_notes,
    ):

        self.last_processing_error = None

        self.status_label.configure(
            text="✓ COMPLETE",
            text_color="#6DD58C",
        )

        self.processing_label.configure(
            text=(
                "Meeting processed successfully "
                "and saved."
            )
        )

        self.notes_box.configure(
            state="normal"
        )

        self.notes_box.delete(
            "1.0",
            "end",
        )

        self.notes_box.insert(
            "1.0",
            text_notes,
        )

        self.notes_box.configure(
            state="disabled"
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
    # PROCESSING FAILED
    # ========================================================

    def processing_failed(
        self,
        error,
    ):

        print(
            "Processing error:",
            error,
        )

        if (
            self.audio_saved
            and self.is_network_error(
                error
            )
        ):

            self.status_label.configure(
                text="⚠ NETWORK ISSUE",
                text_color="#F4C95D",
            )

            self.processing_label.configure(
                text=(
                    "Your recording is safe. "
                    "Reconnect to the internet and "
                    "click Retry Processing."
                )
            )

            self.retry_button.configure(
                state="normal"
            )

            # Important:
            # prevent starting another meeting because
            # current root WAVs could be overwritten.
            self.start_button.configure(
                state="disabled"
            )

            self.stop_button.configure(
                state="disabled"
            )

            return

        self.status_label.configure(
            text="✕ ERROR",
            text_color="#FF6B6B",
        )

        self.processing_label.configure(
            text=str(error)
        )

        if self.audio_saved:

            self.retry_button.configure(
                state="normal"
            )

        else:

            self.start_button.configure(
                state="normal"
            )

            self.meeting_name_entry.configure(
                state="normal"
            )

    # ========================================================
    # DOWNLOAD NOTES
    # ========================================================

    def download_notes(self):

        if not self.current_text_notes:

            self.set_status(
                "No meeting notes are available."
            )

            return

        safe_name = (
            self.current_meeting_name
            or "meeting"
        )

        safe_name = (
            safe_name
            .replace(" ", "_")
        )

        file_path = (
            filedialog
            .asksaveasfilename(
                title="Download Meeting Notes",
                defaultextension=".txt",
                filetypes=[
                    (
                        "Text Document",
                        "*.txt",
                    )
                ],
                initialfile=(
                    f"{safe_name}_notes.txt"
                ),
            )
        )

        if not file_path:
            return

        Path(
            file_path
        ).write_text(
            self.current_text_notes,
            encoding="utf-8",
        )

        self.set_status(
            "✓ Meeting notes downloaded."
        )

    # ========================================================
    # SEND TO WHATSAPP
    # ========================================================

    def send_to_whatsapp(self):

        if not self.current_whatsapp_text:

            self.set_status(
                "No WhatsApp summary is available."
            )

            return

        encoded_text = quote(
            self.current_whatsapp_text
        )

        whatsapp_url = (
            "https://wa.me/"
            f"?text={encoded_text}"
        )

        webbrowser.open(
            whatsapp_url
        )

        self.set_status(
            (
                "WhatsApp opened with your "
                "meeting summary ready to send."
            )
        )

    # ========================================================
    # VIEW TRANSCRIPT
    # ========================================================

    def show_transcript(self):

        try:

            transcript = (
                Path(
                    "combined_transcript.txt"
                )
                .read_text(
                    encoding="utf-8"
                )
            )

        except FileNotFoundError:

            self.set_status(
                "Transcript file not found."
            )

            return

        window = ctk.CTkToplevel(
            self
        )

        window.title(
            "Meeting Transcript"
        )

        window.geometry(
            "780x650"
        )

        title = ctk.CTkLabel(
            window,
            text="Meeting Transcript",
            font=ctk.CTkFont(
                size=22,
                weight="bold",
            ),
        )

        title.pack(
            pady=(20, 10)
        )

        textbox = ctk.CTkTextbox(
            window,
            wrap="word",
            corner_radius=12,
        )

        textbox.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=(0, 25),
        )

        textbox.insert(
            "1.0",
            transcript,
        )

        textbox.configure(
            state="disabled"
        )

    # ========================================================
    # OPEN SAVED MEETING
    # ========================================================

    def open_meeting_folder(self):

        if not self.current_meeting_directory:

            self.set_status(
                "No saved meeting is available."
            )

            return

        try:

            os.startfile(
                self.current_meeting_directory
            )

        except Exception as error:

            self.set_status(
                f"Could not open folder: {error}"
            )

    # ========================================================
    # OUTPUT BUTTON HELPERS
    # ========================================================

    def enable_output_buttons(self):

        self.transcript_button.configure(
            state="normal"
        )

        self.download_button.configure(
            state="normal"
        )

        self.whatsapp_button.configure(
            state="normal"
        )

        self.folder_button.configure(
            state="normal"
        )

    def disable_output_buttons(self):

        self.transcript_button.configure(
            state="disabled"
        )

        self.download_button.configure(
            state="disabled"
        )

        self.whatsapp_button.configure(
            state="disabled"
        )

        self.folder_button.configure(
            state="disabled"
        )

    # ========================================================
    # STATUS
    # ========================================================

    def set_status(
        self,
        message,
    ):

        self.processing_label.configure(
            text=message
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app = MeetingAssistantApp()

    app.mainloop()