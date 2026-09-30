import zipfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import backup
from schemas.recording import RecordingSettings


class RecordingBackupTests(unittest.TestCase):
    def test_archive_keeps_camera_folders_and_skips_active_clip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "recordings"
            camera = source / "Entrance"
            camera.mkdir(parents=True)
            finished = camera / "finished.avi"
            active = camera / "active.avi"
            finished.write_bytes(b"finished clip")
            active.write_bytes(b"incomplete clip")
            with patch.object(backup, "get_recording_settings", return_value=RecordingSettings(directory=str(source))), \
                    patch.object(backup, "active_recording_paths", return_value={active.resolve()}):
                destination = root / "backups" / "recordings.zip"
                backup.create_recordings_archive(destination)

            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(archive.namelist(), ["Entrance/finished.avi"])
                self.assertEqual(archive.read("Entrance/finished.avi"), b"finished clip")
            self.assertFalse(destination.with_name(destination.name + ".partial").exists())

    def test_archive_rejects_no_completed_clips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "recordings"
            source.mkdir()
            with patch.object(backup, "get_recording_settings", return_value=RecordingSettings(directory=str(source))), \
                    patch.object(backup, "active_recording_paths", return_value=set()):
                with self.assertRaisesRegex(backup.BackupError, "No completed recordings"):
                    backup.create_recordings_archive(root / "backups" / "recordings.zip")
