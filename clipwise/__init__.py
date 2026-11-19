"""Clipwise: Intelligent YouTube Long-to-Shorts Processing Engine."""

__version__ = "1.0.0"

# Fix compatibility between faster-whisper and newer PyAV versions (14+)
# Newer PyAV versions removed the 'metadata_errors' keyword from av.open()
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass
