import threading
import time

import customtkinter as ctk

from audio.recorder import MeetingRecorder
from transcription.transcriber import transcribe_meeting
from intelligence.summarizer import summarize_meeting


# ============================================================
# CUSTOMTKINTER CONFIG
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ============================================================
# APPLICATION
# ============================================================

class MeetingAssistantApp(
    ctk.CTk
):

    def __init__(self):

        super().__init__()

        # ----------------------------------------------------
        # WINDOW
        # ----------------------------------------------------

        self.title(
            "WhatsApp Meeting Assistant"
        )

        self.geometry(
            "850x700"
        )

        self.minsize(
            750,
            600,
        )

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.recorder = None

        self.recording = False

        self.start_time = None

        # ----------------------------------------------------
        # GRID
        # ----------------------------------------------------

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        self.grid_rowconfigure(
            6,
            weight=1,
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        self.title_label = (
            ctk.CTkLabel(
                self,
                text=(
                    "WhatsApp Meeting Assistant"
                ),
                font=ctk.CTkFont(
                    size=28,
                    weight="bold",
                ),
            )
        )

        self.title_label.grid(
            row=0,
            column=0,
            padx=30,
            pady=(
                30,
                10,
            ),
        )

        # ----------------------------------------------------
        # MEETING NAME
        # ----------------------------------------------------

        self.meeting_name_entry = (
            ctk.CTkEntry(
                self,
                placeholder_text=(
                    "Enter meeting name..."
                ),
                height=42,
            )
        )

        self.meeting_name_entry.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=80,
            pady=10,
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_label = (
            ctk.CTkLabel(
                self,
                text="● READY",
                font=ctk.CTkFont(
                    size=18,
                    weight="bold",
                ),
            )
        )

        self.status_label.grid(
            row=2,
            column=0,
            pady=10,
        )

        # ----------------------------------------------------
        # TIMER
        # ----------------------------------------------------

        self.timer_label = (
            ctk.CTkLabel(
                self,
                text="00:00",
                font=ctk.CTkFont(
                    size=36,
                    weight="bold",
                ),
            )
        )

        self.timer_label.grid(
            row=3,
            column=0,
            pady=10,
        )

        # ----------------------------------------------------
        # BUTTON FRAME
        # ----------------------------------------------------

        self.button_frame = (
            ctk.CTkFrame(
                self,
                fg_color="transparent",
            )
        )

        self.button_frame.grid(
            row=4,
            column=0,
            pady=15,
        )

        # ----------------------------------------------------
        # START BUTTON
        # ----------------------------------------------------

        self.start_button = (
            ctk.CTkButton(
                self.button_frame,
                text="START MEETING",
                width=180,
                height=45,
                command=self.start_meeting,
            )
        )

        self.start_button.grid(
            row=0,
            column=0,
            padx=10,
        )

        # ----------------------------------------------------
        # STOP BUTTON
        # ----------------------------------------------------

        self.stop_button = (
            ctk.CTkButton(
                self.button_frame,
                text="STOP & SUMMARIZE",
                width=180,
                height=45,
                command=self.stop_meeting,
                state="disabled",
            )
        )

        self.stop_button.grid(
            row=0,
            column=1,
            padx=10,
        )

        # ----------------------------------------------------
        # PROCESSING LABEL
        # ----------------------------------------------------

        self.processing_label = (
            ctk.CTkLabel(
                self,
                text="",
                font=ctk.CTkFont(
                    size=14,
                ),
            )
        )

        self.processing_label.grid(
            row=5,
            column=0,
            pady=5,
        )

        # ----------------------------------------------------
        # NOTES DISPLAY
        # ----------------------------------------------------

        self.notes_box = (
            ctk.CTkTextbox(
                self,
                wrap="word",
                font=ctk.CTkFont(
                    size=14,
                ),
            )
        )

        self.notes_box.grid(
            row=6,
            column=0,
            sticky="nsew",
            padx=40,
            pady=(
                10,
                20,
            ),
        )

        self.notes_box.insert(
            "1.0",
            (
                "Meeting notes will "
                "appear here."
            ),
        )

        self.notes_box.configure(
            state="disabled"
        )

        # ----------------------------------------------------
        # TRANSCRIPT BUTTON
        # ----------------------------------------------------

        self.transcript_button = (
            ctk.CTkButton(
                self,
                text="VIEW TRANSCRIPT",
                command=(
                    self.show_transcript
                ),
                state="disabled",
            )
        )

        self.transcript_button.grid(
            row=7,
            column=0,
            pady=(
                0,
                25,
            ),
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

            self.recorder = (
                MeetingRecorder()
            )

            self.recorder.start()

        except Exception as error:

            self.set_status(
                f"Recording error: {error}"
            )

            return

        self.recording = True

        self.start_time = time.time()

        self.status_label.configure(
            text="● RECORDING"
        )

        self.processing_label.configure(
            text=(
                "Meeting is being recorded..."
            )
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

        minutes = (
            elapsed // 60
        )

        seconds = (
            elapsed % 60
        )

        self.timer_label.configure(
            text=(
                f"{minutes:02d}:"
                f"{seconds:02d}"
            )
        )

        self.after(
            1000,
            self.update_timer,
        )


    # ========================================================
    # STOP MEETING
    # ========================================================

    def stop_meeting(self):

        if not self.recording:
            return

        self.recording = False

        self.stop_button.configure(
            state="disabled"
        )

        self.status_label.configure(
            text="● PROCESSING"
        )

        self.processing_label.configure(
            text="Stopping recording..."
        )

        # Heavy AI/network processing must NOT
        # run on the GUI thread.
        worker = threading.Thread(
            target=self.process_meeting,
            daemon=True,
        )

        worker.start()


    # ========================================================
    # PROCESS COMPLETE MEETING
    # ========================================================

    def process_meeting(self):

        try:

            # -----------------------------------------------
            # STOP AUDIO
            # -----------------------------------------------

            self.update_processing(
                "Saving recording..."
            )

            recording_result = (
                self.recorder.stop()
            )

            print(
                recording_result
            )

            # -----------------------------------------------
            # TRANSCRIPTION
            # -----------------------------------------------

            self.update_processing(
                "Transcribing speakers..."
            )

            transcript_result = (
                transcribe_meeting()
            )

            print(
                transcript_result
            )

            # -----------------------------------------------
            # MEETING INTELLIGENCE
            # -----------------------------------------------

            self.update_processing(
                "Generating meeting notes..."
            )

            notes, text_notes = (
                summarize_meeting()
            )

            # -----------------------------------------------
            # DISPLAY RESULT
            # -----------------------------------------------

            self.after(
                0,
                lambda: (
                    self.display_notes(
                        text_notes
                    )
                ),
            )

        except Exception as error:

            self.after(
                0,
                lambda err=error: (
                    self.processing_failed(
                        err
                    )
                ),
            )


    # ========================================================
    # THREAD-SAFE STATUS UPDATE
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
    # DISPLAY NOTES
    # ========================================================

    def display_notes(
        self,
        text_notes,
    ):

        self.status_label.configure(
            text="✓ COMPLETE"
        )

        self.processing_label.configure(
            text=(
                "Meeting processed successfully."
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

        self.transcript_button.configure(
            state="normal"
        )

        self.start_button.configure(
            state="normal"
        )

        self.meeting_name_entry.configure(
            state="normal"
        )


    # ========================================================
    # VIEW TRANSCRIPT
    # ========================================================

    def show_transcript(self):

        try:

            with open(
                "combined_transcript.txt",
                "r",
                encoding="utf-8",
            ) as file:

                transcript = file.read()

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
            "750x600"
        )

        textbox = ctk.CTkTextbox(
            window,
            wrap="word",
        )

        textbox.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=20,
        )

        textbox.insert(
            "1.0",
            transcript,
        )

        textbox.configure(
            state="disabled"
        )


    # ========================================================
    # FAILURE
    # ========================================================

    def processing_failed(
        self,
        error,
    ):

        self.status_label.configure(
            text="✕ ERROR"
        )

        self.processing_label.configure(
            text=str(error)
        )

        self.start_button.configure(
            state="normal"
        )

        self.stop_button.configure(
            state="disabled"
        )

        self.meeting_name_entry.configure(
            state="normal"
        )


    # ========================================================
    # SIMPLE STATUS
    # ========================================================

    def set_status(
        self,
        message,
    ):

        self.processing_label.configure(
            text=message
        )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app = MeetingAssistantApp()

    app.mainloop()