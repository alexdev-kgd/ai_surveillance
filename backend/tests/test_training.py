import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from schemas.training import TrainingClassLabel, TrainingStartRequest
from services.dataset_scan import scan_dataset_classes
from services.training import (
    _load_crop_module,
    _run_job,
    cancel_training,
    get_status,
    reset_training_state_for_tests,
    scan_classes,
    start_training,
)
from utils.optical_flow_cache import collect_videos_for_precompute, precompute_missing_flow


def _write_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def _make_split(root: Path, class_name: str = "assault") -> Path:
    _write_video(root / class_name / "clip.mp4")
    return root


def _frontend_start_payload(**overrides) -> dict:
    payload = {
        "train_dir": "dataset/train",
        "val_dir": "dataset/val",
        "yolo_train_dir": "dataset-cropped/train",
        "yolo_val_dir": "dataset-cropped/val",
        "train_scene_model": True,
        "train_yolo_model": True,
        "prepare_yolo_crops": True,
        "save_plots": False,
        "plot_dir": None,
        "classes": [{"key": "assault", "label": "Нападение"}],
        "epochs": 40,
        "backbone_lr": 1e-5,
        "head_lr": 1e-4,
        "batch_size": 4,
        "weight_decay": 5e-3,
        "dropout": 0.65,
        "label_smoothing": 0.1,
        "patience": 3,
        "fusion": "add",
        "use_class_weights": True,
    }
    payload.update(overrides)
    return payload


def _start_without_running_job(payload: TrainingStartRequest):
    captured = {}

    class DummyThread:
        def __init__(self, target=None, args=(), kwargs=None, **extra):
            captured["target"] = target
            captured["args"] = args

        def start(self):
            return None

        def join(self, timeout=None):
            return None

    with patch("services.training.threading.Thread", DummyThread), patch(
        "services.training._persist_action_labels_sync"
    ), patch("services.training.persist_action_labels"):
        status = start_training(payload, user_id="1")
    return status, captured


class DatasetScanTests(unittest.TestCase):
    def test_missing_val_folder_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = Path(tmp) / "train"
            val = Path(tmp) / "val"
            (train / "assault").mkdir(parents=True)
            (train / "hit").mkdir(parents=True)
            (val / "assault").mkdir(parents=True)
            (train / "assault" / "a.mp4").write_bytes(b"x")
            (train / "hit" / "b.mp4").write_bytes(b"x")
            (val / "assault" / "a.mp4").write_bytes(b"x")

            classes = {item.key: item for item in scan_dataset_classes(str(train), str(val))}
            self.assertTrue(classes["assault"].has_val)
            self.assertFalse(classes["hit"].has_val)
            self.assertEqual(classes["hit"].val_videos, 0)
            self.assertEqual(classes["assault"].train_videos, 1)
            self.assertFalse(classes["hit"].has_yolo_val)

    def test_missing_yolo_val_folder_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = Path(tmp) / "train"
            val = Path(tmp) / "val"
            yolo_train = Path(tmp) / "yolo-train"
            yolo_val = Path(tmp) / "yolo-val"
            (train / "assault").mkdir(parents=True)
            (val / "assault").mkdir(parents=True)
            (yolo_train / "assault").mkdir(parents=True)
            yolo_val.mkdir()
            (train / "assault" / "a.mp4").write_bytes(b"x")
            (val / "assault" / "a.mp4").write_bytes(b"x")
            (yolo_train / "assault" / "a.mp4").write_bytes(b"x")

            classes = {
                item.key: item
                for item in scan_dataset_classes(
                    str(train),
                    str(val),
                    yolo_train_dir=str(yolo_train),
                    yolo_val_dir=str(yolo_val),
                )
            }
            self.assertTrue(classes["assault"].has_val)
            self.assertTrue(classes["assault"].has_yolo_train)
            self.assertFalse(classes["assault"].has_yolo_val)
            self.assertEqual(classes["assault"].yolo_train_videos, 1)

    def test_labels_fall_back_to_folder_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = Path(tmp) / "train"
            val = Path(tmp) / "val"
            (train / "custom_action").mkdir(parents=True)
            val.mkdir()
            classes = scan_dataset_classes(
                str(train),
                str(val),
                labels={"custom_action": "Особая активность"},
            )
            self.assertEqual(classes[0].label, "Особая активность")
            self.assertFalse(classes[0].has_val)


class OpticalFlowCacheTests(unittest.TestCase):
    def test_collect_skips_existing_flow_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            cls = Path(tmp) / "train" / "assault"
            cls.mkdir(parents=True)
            (cls / "ready.mp4").write_bytes(b"x")
            (cls / "ready_flow.npy").write_bytes(b"x")
            (cls / "missing.mp4").write_bytes(b"x")

            jobs = collect_videos_for_precompute([str(Path(tmp) / "train")], skip_existing=True)
            self.assertEqual(len(jobs), 1)
            self.assertTrue(jobs[0][2].endswith("missing.mp4"))

            forced = collect_videos_for_precompute(
                [str(Path(tmp) / "train")], skip_existing=False
            )
            self.assertEqual(len(forced), 2)

    def test_precompute_writes_only_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            cls = Path(tmp) / "val" / "normal"
            cls.mkdir(parents=True)
            missing = cls / "clip.mp4"
            existing = cls / "done.mp4"
            missing.write_bytes(b"x")
            existing.write_bytes(b"x")
            (cls / "done_flow.npy").write_bytes(b"old")

            def fake_compute(_path):
                import numpy as np

                return np.zeros((2, 2, 2, 2), dtype=np.float16)

            stats = precompute_missing_flow(
                [str(Path(tmp) / "val")],
                skip_existing=True,
                show_progress_bar=False,
                compute_fn=fake_compute,
            )
            self.assertEqual(stats["queued"], 1)
            self.assertEqual(stats["processed"], 1)
            self.assertTrue((cls / "clip_flow.npy").is_file())
            self.assertEqual((cls / "done_flow.npy").read_bytes(), b"old")


class TrainingServiceTests(unittest.TestCase):
    def setUp(self):
        reset_training_state_for_tests()

    def tearDown(self):
        reset_training_state_for_tests()

    def test_scan_classes_reports_missing_train_dir(self):
        result = scan_classes(os.path.join("no", "such", "train"), os.path.join("no", "such", "val"))
        self.assertFalse(result.train_exists)
        self.assertEqual(result.classes, [])
        self.assertIn("тренировочной", result.error or "")

    def test_start_rejects_when_no_model_selected(self):
        payload = TrainingStartRequest(
            train_dir="dataset/train",
            val_dir="dataset/val",
            train_scene_model=False,
            train_yolo_model=False,
            classes=[TrainingClassLabel(key="assault", label="Нападение")],
        )
        with self.assertRaises(ValueError):
            start_training(payload, user_id="1")

    def test_cancel_without_running_job_fails(self):
        reset_training_state_for_tests()
        with self.assertRaises(RuntimeError):
            cancel_training()

    def test_start_rejects_missing_directories(self):
        payload = TrainingStartRequest(
            train_dir="missing-train",
            val_dir="missing-val",
            train_scene_model=True,
            train_yolo_model=False,
            classes=[TrainingClassLabel(key="assault", label="Нападение")],
        )
        with self.assertRaises(ValueError):
            start_training(payload, user_id="1")

    def test_start_and_cancel_with_mocked_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = Path(tmp) / "train"
            val = Path(tmp) / "val"
            (train / "assault").mkdir(parents=True)
            (val / "assault").mkdir(parents=True)
            (train / "assault" / "a.mp4").write_bytes(b"x")
            (val / "assault" / "a.mp4").write_bytes(b"x")

            payload = TrainingStartRequest(
                train_dir=str(train),
                val_dir=str(val),
                train_scene_model=True,
                train_yolo_model=False,
                prepare_yolo_crops=False,
                classes=[TrainingClassLabel(key="assault", label="Нападение")],
            )

            with patch("services.training._run_job"), patch(
                "services.training._persist_action_labels_sync"
            ), patch("services.training.persist_action_labels"):
                status = start_training(payload, user_id="1")
                self.assertTrue(status.can_cancel)
                self.assertIn(status.state, {"precomputing", "training"})
                cancelled = cancel_training()
                self.assertEqual(cancelled.message, "Отмена обучения...")

            self.assertTrue(get_status().can_cancel or get_status().state != "idle")


class ScriptModuleLoadTests(unittest.TestCase):
    def test_crop_module_dataclasses_load_without_sys_modules_error(self):
        import services.training as training_mod

        training_mod._crop_module = None
        module = _load_crop_module()
        self.assertTrue(hasattr(module.Track, "__dataclass_fields__"))
        self.assertTrue(hasattr(module.VideoResult, "__dataclass_fields__"))
        result = module.VideoResult(source=Path("clip.mp4"))
        self.assertEqual(result.crops_created, 0)


class TrainingStartScenarioTests(unittest.TestCase):
    def setUp(self):
        reset_training_state_for_tests()

    def tearDown(self):
        reset_training_state_for_tests()

    def test_frontend_payload_is_accepted_for_all_three_modes(self):
        both = TrainingStartRequest(**_frontend_start_payload())
        yolo_only = TrainingStartRequest(
            **_frontend_start_payload(
                train_scene_model=False,
                train_yolo_model=True,
                prepare_yolo_crops=False,
            )
        )
        scene_only = TrainingStartRequest(
            **_frontend_start_payload(
                train_scene_model=True,
                train_yolo_model=False,
                prepare_yolo_crops=False,
            )
        )
        self.assertTrue(both.train_scene_model and both.train_yolo_model)
        self.assertTrue(yolo_only.train_yolo_model and not yolo_only.train_scene_model)
        self.assertTrue(scene_only.train_scene_model and not scene_only.train_yolo_model)
        self.assertIsNone(both.plot_dir)

    def test_start_both_scene_and_yolo_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = _make_split(Path(tmp) / "train")
            val = _make_split(Path(tmp) / "val")
            yolo_train = _make_split(Path(tmp) / "yolo-train")
            yolo_val = _make_split(Path(tmp) / "yolo-val")
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(train),
                    val_dir=str(val),
                    yolo_train_dir=str(yolo_train),
                    yolo_val_dir=str(yolo_val),
                    train_scene_model=True,
                    train_yolo_model=True,
                    prepare_yolo_crops=False,
                )
            )
            status, captured = _start_without_running_job(payload)
            self.assertTrue(status.can_cancel)
            self.assertIn(status.state, {"precomputing", "cropping", "training"})
            self.assertIsNone(status.error)
            self.assertEqual(status.message, "Запуск обучения...")
            job_payload, class_items, _user_id, temp_paths = captured["args"]
            self.assertTrue(job_payload.train_scene_model)
            self.assertTrue(job_payload.train_yolo_model)
            self.assertEqual(class_items, [("assault", "Нападение")])
            self.assertEqual(len(temp_paths), 4)

    def test_start_both_with_missing_yolo_dirs_prepares_crops(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = _make_split(Path(tmp) / "train")
            val = _make_split(Path(tmp) / "val")
            yolo_train = Path(tmp) / "yolo-train"
            yolo_val = Path(tmp) / "yolo-val"
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(train),
                    val_dir=str(val),
                    yolo_train_dir=str(yolo_train),
                    yolo_val_dir=str(yolo_val),
                    train_scene_model=True,
                    train_yolo_model=True,
                    prepare_yolo_crops=True,
                )
            )
            status, captured = _start_without_running_job(payload)
            self.assertTrue(status.can_cancel)
            self.assertIsNone(status.error)
            self.assertEqual(len(captured["args"][3]), 4)

    def test_start_yolo_model_only_with_existing_crops(self):
        with tempfile.TemporaryDirectory() as tmp:
            yolo_train = _make_split(Path(tmp) / "yolo-train")
            yolo_val = _make_split(Path(tmp) / "yolo-val")
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(Path(tmp) / "unused-train"),
                    val_dir=str(Path(tmp) / "unused-val"),
                    yolo_train_dir=str(yolo_train),
                    yolo_val_dir=str(yolo_val),
                    train_scene_model=False,
                    train_yolo_model=True,
                    prepare_yolo_crops=False,
                )
            )
            status, captured = _start_without_running_job(payload)
            self.assertTrue(status.can_cancel)
            self.assertIsNone(status.error)
            job_payload, _class_items, _user_id, temp_paths = captured["args"]
            self.assertFalse(job_payload.train_scene_model)
            self.assertTrue(job_payload.train_yolo_model)
            self.assertEqual(len(temp_paths), 2)

    def test_start_yolo_model_only_prepares_crops_from_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = _make_split(Path(tmp) / "train")
            val = _make_split(Path(tmp) / "val")
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(train),
                    val_dir=str(val),
                    yolo_train_dir=str(Path(tmp) / "yolo-train"),
                    yolo_val_dir=str(Path(tmp) / "yolo-val"),
                    train_scene_model=False,
                    train_yolo_model=True,
                    prepare_yolo_crops=True,
                )
            )
            status, captured = _start_without_running_job(payload)
            self.assertTrue(status.can_cancel)
            self.assertIsNone(status.error)
            job_payload, _class_items, _user_id, temp_paths = captured["args"]
            self.assertFalse(job_payload.train_scene_model)
            self.assertTrue(job_payload.prepare_yolo_crops)
            self.assertEqual(len(temp_paths), 2)

    def test_start_scene_model_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = _make_split(Path(tmp) / "train")
            val = _make_split(Path(tmp) / "val")
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(train),
                    val_dir=str(val),
                    yolo_train_dir=str(Path(tmp) / "yolo-train"),
                    yolo_val_dir=str(Path(tmp) / "yolo-val"),
                    train_scene_model=True,
                    train_yolo_model=False,
                    prepare_yolo_crops=False,
                )
            )
            status, captured = _start_without_running_job(payload)
            self.assertTrue(status.can_cancel)
            self.assertIsNone(status.error)
            job_payload, _class_items, _user_id, temp_paths = captured["args"]
            self.assertTrue(job_payload.train_scene_model)
            self.assertFalse(job_payload.train_yolo_model)
            self.assertEqual(len(temp_paths), 2)


class TrainingJobScenarioTests(unittest.TestCase):
    def setUp(self):
        reset_training_state_for_tests()

    def tearDown(self):
        reset_training_state_for_tests()

    def _fake_train(self, trained):
        def fake_train(
            payload,
            names,
            train_dir,
            val_dir,
            temp_best,
            temp_last,
            plot_prefix,
            label,
        ):
            trained.append((label, plot_prefix, Path(train_dir).name, names))
            Path(temp_best).write_bytes(b"best")
            Path(temp_last).write_bytes(b"last")
            return {"train_loss": [0.2], "val_loss": [0.3]}

        return fake_train

    def _fake_prepare(self):
        def fake_prepare(scene_dir, yolo_dir, label):
            _write_video(Path(yolo_dir) / "assault" / "crop.mp4")

        return fake_prepare

    def test_run_job_trains_scene_and_yolo(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = _make_split(Path(tmp) / "train")
            val = _make_split(Path(tmp) / "val")
            yolo_train = _make_split(Path(tmp) / "yolo-train")
            yolo_val = _make_split(Path(tmp) / "yolo-val")
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(train),
                    val_dir=str(val),
                    yolo_train_dir=str(yolo_train),
                    yolo_val_dir=str(yolo_val),
                    train_scene_model=True,
                    train_yolo_model=True,
                    prepare_yolo_crops=False,
                )
            )
            trained = []
            temp_paths = [
                Path(tmp) / "scene_best.pth",
                Path(tmp) / "scene_last.pth",
                Path(tmp) / "yolo_best.pth",
                Path(tmp) / "yolo_last.pth",
            ]
            with patch(
                "services.training._train_one_model", self._fake_train(trained)
            ), patch("services.training._promote_checkpoint") as promote, patch(
                "services.training._reload_inference_model"
            ) as reload, patch(
                "services.training._prepare_yolo_crops"
            ) as prepare:
                _run_job(payload, [("assault", "Нападение")], "1", temp_paths)

            self.assertEqual(
                [item[0] for item in trained],
                ["Модель полной сцены", "Модель YOLO-вырезок"],
            )
            self.assertEqual([item[1] for item in trained], ["train_scene", "train_yolo"])
            self.assertEqual(promote.call_count, 2)
            self.assertEqual(
                [call.kwargs.get("target") or call.args[1] for call in reload.call_args_list],
                ["scene", "yolo"],
            )
            prepare.assert_not_called()
            status = get_status()
            self.assertEqual(status.state, "completed")
            self.assertIsNone(status.error)
            self.assertIn("полной сцены", status.message)
            self.assertIn("YOLO-вырезок", status.message)

    def test_run_job_trains_yolo_only_and_prepares_crops(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = _make_split(Path(tmp) / "train")
            val = _make_split(Path(tmp) / "val")
            yolo_train = Path(tmp) / "yolo-train"
            yolo_val = Path(tmp) / "yolo-val"
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(train),
                    val_dir=str(val),
                    yolo_train_dir=str(yolo_train),
                    yolo_val_dir=str(yolo_val),
                    train_scene_model=False,
                    train_yolo_model=True,
                    prepare_yolo_crops=True,
                )
            )
            trained = []
            temp_paths = [Path(tmp) / "yolo_best.pth", Path(tmp) / "yolo_last.pth"]
            with patch(
                "services.training._train_one_model", self._fake_train(trained)
            ), patch("services.training._promote_checkpoint") as promote, patch(
                "services.training._reload_inference_model"
            ) as reload, patch(
                "services.training._prepare_yolo_crops", self._fake_prepare()
            ):
                _run_job(payload, [("assault", "Нападение")], "1", temp_paths)

            self.assertEqual([item[0] for item in trained], ["Модель YOLO-вырезок"])
            self.assertEqual(promote.call_count, 1)
            self.assertEqual(reload.call_args.kwargs.get("target") or reload.call_args.args[1], "yolo")
            status = get_status()
            self.assertEqual(status.state, "completed")
            self.assertIsNone(status.error)
            self.assertEqual(status.message, "Обучение завершено: YOLO-вырезки")

    def test_run_job_trains_scene_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            train = _make_split(Path(tmp) / "train")
            val = _make_split(Path(tmp) / "val")
            payload = TrainingStartRequest(
                **_frontend_start_payload(
                    train_dir=str(train),
                    val_dir=str(val),
                    train_scene_model=True,
                    train_yolo_model=False,
                    prepare_yolo_crops=False,
                )
            )
            trained = []
            temp_paths = [Path(tmp) / "scene_best.pth", Path(tmp) / "scene_last.pth"]
            with patch(
                "services.training._train_one_model", self._fake_train(trained)
            ), patch("services.training._promote_checkpoint") as promote, patch(
                "services.training._reload_inference_model"
            ) as reload, patch(
                "services.training._prepare_yolo_crops"
            ) as prepare:
                _run_job(payload, [("assault", "Нападение")], "1", temp_paths)

            self.assertEqual([item[0] for item in trained], ["Модель полной сцены"])
            self.assertEqual(promote.call_count, 1)
            self.assertEqual(reload.call_args.kwargs.get("target") or reload.call_args.args[1], "scene")
            prepare.assert_not_called()
            status = get_status()
            self.assertEqual(status.state, "completed")
            self.assertIsNone(status.error)
            self.assertEqual(status.message, "Обучение завершено: полная сцена")


if __name__ == "__main__":
    unittest.main()
