import json
import re
import shutil

from datetime import datetime
from pathlib import Path


class MeetingStore:
    """
    Stores all generated files belonging to one meeting
    inside a timestamped meeting directory.
    """

    def __init__(self, project_root=None):

        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent

        self.project_root = Path(project_root)

        self.meetings_root = (
            self.project_root
            / "data"
            / "meetings"
        )

        self.meetings_root.mkdir(
            parents=True,
            exist_ok=True,
        )


    # SLUG

    def _slugify(self, text):
        """
        Converts meeting name into a safe folder name.
        """

        text = text.strip().lower()

        text = re.sub(
            r"[^a-z0-9]+",
            "-",
            text,
        )

        text = text.strip("-")

        if not text:
            text = "meeting"

        return text


    # CREATE DIRECTORY

    def create_meeting_directory(
        self,
        meeting_name,
    ):

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        slug = self._slugify(
            meeting_name
        )

        directory_name = (
            f"{timestamp}_{slug}"
        )

        meeting_directory = (
            self.meetings_root
            / directory_name
        )

        meeting_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        return meeting_directory


    # COPY FILE
   
    def _copy_if_exists(
        self,
        filename,
        destination,
    ):

        source = (
            self.project_root
            / filename
        )

        if not source.exists():
            return None

        target = (
            destination
            / filename
        )

        shutil.copy2(
            source,
            target,
        )

        return target


    # ========================================================
    # SAVE COMPLETE MEETING
    # ========================================================

    def save_meeting(
        self,
        meeting_name,
        whatsapp_text=None,
        duration=None,
    ):

        meeting_directory = (
            self.create_meeting_directory(
                meeting_name
            )
        )

        files_to_copy = [
            "mic_raw.wav",
            "system_raw.wav",
            "meeting.wav",
            "my_transcript.txt",
            "client_transcript.txt",
            "combined_transcript.txt",
            "meeting_notes.json",
            "meeting_notes.txt",
        ]

        saved_files = {}

        for filename in files_to_copy:

            saved_path = self._copy_if_exists(
                filename,
                meeting_directory,
            )

            if saved_path:

                saved_files[
                    filename
                ] = str(saved_path)

        # ----------------------------------------------------
        # WHATSAPP VERSION
        # ----------------------------------------------------

        if whatsapp_text:

            whatsapp_file = (
                meeting_directory
                / "whatsapp_notes.txt"
            )

            whatsapp_file.write_text(
                whatsapp_text,
                encoding="utf-8",
            )

            saved_files[
                "whatsapp_notes.txt"
            ] = str(whatsapp_file)

        # ----------------------------------------------------
        # METADATA
        # ----------------------------------------------------

        metadata = {
            "meeting_name": meeting_name,
            "created_at": datetime.now().isoformat(),
            "duration_seconds": duration,
            "files": saved_files,
        }

        metadata_file = (
            meeting_directory
            / "metadata.json"
        )

        metadata_file.write_text(
            json.dumps(
                metadata,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return meeting_directory