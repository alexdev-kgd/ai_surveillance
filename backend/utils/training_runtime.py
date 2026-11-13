class TrainingCancelled(Exception):
    """Raised when a web-initiated training job is cancelled."""


def raise_if_cancelled(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise TrainingCancelled()
