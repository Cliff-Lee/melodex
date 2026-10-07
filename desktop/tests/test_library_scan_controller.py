from pathlib import Path

from melodex.library_scan_controller import LibraryScanController


class FakeRunner:
    def __init__(
        self,
        data_dir,
        roots,
        *,
        on_progress,
        on_done,
        on_error,
    ):
        self.data_dir = Path(data_dir)
        self.roots = [Path(root) for root in roots]
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error
        self.paused = False
        self.started = False
        self.cancelled = False
        self.shutdown_called = False
        self.priorities = []

    def start(self):
        self.started = True

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def prioritize(self, path):
        self.priorities.append(Path(path))
        return True

    def cancel(self):
        self.cancelled = True
        self.paused = False

    def shutdown(self):
        self.shutdown_called = True


def make_controller(tmp_path):
    return LibraryScanController(tmp_path, runner_factory=FakeRunner)


def test_start_and_finish_own_runner_lifecycle(tmp_path):
    controller = make_controller(tmp_path)
    sequence = controller.start([tmp_path / "music"])

    assert sequence == 1
    assert controller.active is True
    assert controller.runner.started is True
    assert controller.runner.roots == [tmp_path / "music"]
    assert controller.roots_key == (str(tmp_path / "music"),)

    assert controller.finish(sequence + 1) is False
    assert controller.active is True

    assert controller.finish(sequence) is True
    assert controller.active is False


def test_worker_callbacks_keep_sequence_identity(tmp_path):
    controller = make_controller(tmp_path)
    progress = []
    done = []
    failed = []
    controller.progress.connect(lambda seq, payload: progress.append((seq, payload)))
    controller.done.connect(lambda seq, payload: done.append((seq, payload)))
    controller.failed.connect(lambda seq, error: failed.append((seq, error)))

    sequence = controller.start([tmp_path / "music"])
    runner = controller.runner
    runner.on_progress({"phase": "metadata"})
    runner.on_done({"tracks": []})
    runner.on_error("boom")

    assert progress == [(sequence, {"phase": "metadata"})]
    assert done == [(sequence, {"tracks": []})]
    assert failed == [(sequence, "boom")]


def test_queue_rescan_only_cancels_when_roots_change(tmp_path):
    controller = make_controller(tmp_path)
    root = tmp_path / "music"
    controller.start([root])

    assert controller.queue_rescan([root]) is False
    assert controller.pending is True
    assert controller.runner.cancelled is False

    controller.clear_pending()
    assert controller.pending is False

    assert controller.queue_rescan([tmp_path / "other"]) is True
    assert controller.pending is True
    assert controller.runner.cancelled is True
    assert controller.take_pending() is True
    assert controller.pending is False


def test_pause_cancel_and_shutdown_delegate_to_worker(tmp_path):
    controller = make_controller(tmp_path)
    controller.start([tmp_path / "music"])

    assert controller.toggle_pause() is True
    assert controller.paused is True
    assert controller.toggle_pause() is False
    assert controller.paused is False

    controller.queue_rescan([tmp_path / "music"])
    assert controller.cancel(clear_pending=True) is True
    assert controller.pending is False
    assert controller.runner.cancelled is True

    runner = controller.runner
    controller.shutdown()
    assert runner.shutdown_called is True
    assert controller.active is False


def test_foreground_directory_intent_is_forwarded_to_active_worker(tmp_path):
    controller = make_controller(tmp_path)
    controller.start([tmp_path / "music"])
    target = tmp_path / "music" / "Artist" / "Album"

    assert controller.prioritize(target) is True
    assert controller.runner.priorities == [target]
