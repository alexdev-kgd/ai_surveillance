import asyncio
import logging
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select, text

from core.db import AsyncSessionLocal, engine
from models.settings import Settings
from schemas.backup import BackupSchedule, BackupScheduleConfig
from services.recording import active_recording_paths, get_recording_settings, resolve_recordings_dir

logger = logging.getLogger(__name__)
BACKUPS_DIR = Path(__file__).resolve().parents[2] / "saved_backups"
RECORDING_BACKUPS_DIR = BACKUPS_DIR / "recordings"
backup_lock = asyncio.Lock()
recording_backup_lock = asyncio.Lock()


class BackupError(Exception):
    pass


def next_run(config: BackupScheduleConfig, now: datetime) -> datetime:
    if config.mode == "interval":
        return now + timedelta(hours=config.interval_hours)
    hour, minute = map(int, config.daily_time.split(":"))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def postgres_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PGPASSWORD"] = engine.url.password or ""
    return environment


def connection_args() -> list[str]:
    url = engine.url
    return [
        "--host", url.host or "localhost", "--port", str(url.port or 5432),
        "--username", url.username or "postgres",
    ]


async def run_postgres_command(
    command: list[str], timeout: int, lock_timeout: bool = False,
) -> None:
    environment = postgres_environment()
    if lock_timeout:
        environment["PGOPTIONS"] = (
            environment.get("PGOPTIONS", "") + " -c lock_timeout=15s"
        ).strip()
    try:
        result = await asyncio.to_thread(
            subprocess.run, command, env=environment,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise BackupError("PostgreSQL command timed out") from exc
    if result.returncode != 0:
        raise BackupError(result.stderr.strip()[-500:] or "PostgreSQL command failed")


async def create_database_dump(path: Path) -> None:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise BackupError("pg_dump is not installed on the server")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        await run_postgres_command([
            pg_dump, "--format=custom", "--no-owner", "--no-privileges",
            *connection_args(), "--file", str(partial),
            engine.url.database or "postgres",
        ], timeout=300)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


async def create_scheduled_dump() -> Path:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"ai_surveillance_{datetime.now():%Y-%m-%d_%H-%M-%S_%f}.dump"
    path = BACKUPS_DIR / name
    await create_database_dump(path)
    return path


def create_recordings_archive(path: Path) -> None:
    source = resolve_recordings_dir(get_recording_settings().directory)
    if not source.is_dir():
        raise BackupError("Recording directory does not exist")
    active = active_recording_paths()
    clips = sorted(p for p in source.rglob("*.avi") if p.is_file() and not p.is_symlink()
                   and p.resolve() not in active)
    if not clips:
        raise BackupError("No completed recordings to back up")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for clip in clips:
                if clip.resolve() in active_recording_paths():
                    continue
                archive.write(clip, clip.relative_to(source))
            if not archive.namelist():
                raise BackupError("No completed recordings to back up")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


async def create_scheduled_recordings_archive() -> Path:
    path = RECORDING_BACKUPS_DIR / f"recordings_{datetime.now():%Y-%m-%d_%H-%M-%S_%f}.zip"
    await asyncio.to_thread(create_recordings_archive, path)
    return path


async def validate_database_dump(path: Path) -> str:
    pg_restore = shutil.which("pg_restore")
    if not pg_restore:
        raise BackupError("pg_restore is not installed on the server")
    with path.open("rb") as archive:
        signature = archive.read(5)
    if signature != b"PGDMP":
        raise BackupError("Only PostgreSQL custom-format .dump files are supported")
    await run_postgres_command([pg_restore, "--list", str(path)], timeout=60)
    return pg_restore


async def restore_database_dump(path: Path, pg_restore: str) -> None:
    await run_postgres_command([
        pg_restore, "--clean", "--if-exists", "--single-transaction",
        "--exit-on-error", "--no-owner", "--no-privileges",
        *connection_args(), "--dbname", engine.url.database or "postgres",
        str(path),
    ], timeout=900, lock_timeout=True)
    await engine.dispose()


async def get_schedule(db, key: str = "backup_schedule") -> BackupSchedule:
    row = (await db.execute(select(Settings).where(Settings.name == key))).scalar_one_or_none()
    return BackupSchedule(**row.settings) if row else BackupSchedule()


async def save_schedule(db, schedule: BackupSchedule, user_id: str = "system", key: str = "backup_schedule") -> None:
    row = (await db.execute(select(Settings).where(Settings.name == key))).scalar_one_or_none()
    if row is None:
        row = Settings(name=key, settings=schedule.model_dump(mode="json"), updated_by=user_id)
        db.add(row)
    else:
        row.settings = schedule.model_dump(mode="json")
        row.updated_by = user_id
    await db.commit()


async def run_due_backup() -> None:
    async with backup_lock:
        async with AsyncSessionLocal() as db:
            # Coordinate scheduler loops when the API runs with multiple workers.
            locked = (await db.execute(
                text("SELECT pg_try_advisory_xact_lock(768527361)")
            )).scalar_one()
            if not locked:
                return
            schedule = await get_schedule(db)
            if not schedule.enabled:
                return
            now = datetime.now().astimezone()
            if schedule.next_run_at is None:
                schedule.next_run_at = next_run(schedule, now)
                await save_schedule(db, schedule)
                return
            if schedule.next_run_at > now:
                return
            try:
                path = await create_scheduled_dump()
                schedule.last_run_at = now
                schedule.last_error = None
                logger.info("Automatic database backup saved to %s", path)
            except (OSError, BackupError) as exc:
                schedule.last_error = str(exc)[:500]
                logger.exception("Automatic database backup failed")
            schedule.next_run_at = next_run(schedule, datetime.now().astimezone())
            await save_schedule(db, schedule)


async def backup_scheduler() -> None:
    while True:
        try:
            await run_due_backup()
            await run_due_recording_backup()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Backup scheduler check failed")
        await asyncio.sleep(30)


async def run_due_recording_backup() -> None:
    async with recording_backup_lock:
        async with AsyncSessionLocal() as db:
            locked = (await db.execute(text("SELECT pg_try_advisory_xact_lock(768527362)"))).scalar_one()
            if not locked:
                return
            schedule = await get_schedule(db, "recording_backup_schedule")
            if not schedule.enabled:
                return
            now = datetime.now().astimezone()
            if schedule.next_run_at is None:
                schedule.next_run_at = next_run(schedule, now)
                await save_schedule(db, schedule, key="recording_backup_schedule")
                return
            if schedule.next_run_at > now:
                return
            try:
                path = await create_scheduled_recordings_archive()
                schedule.last_run_at = now
                schedule.last_error = None
                logger.info("Automatic recording backup saved to %s", path)
            except (OSError, BackupError, zipfile.BadZipFile) as exc:
                schedule.last_error = str(exc)[:500]
                logger.exception("Automatic recording backup failed")
            schedule.next_run_at = next_run(schedule, datetime.now().astimezone())
            await save_schedule(db, schedule, key="recording_backup_schedule")
