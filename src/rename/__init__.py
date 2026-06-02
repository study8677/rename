"""rename — keep your AI coding sessions named after what they're about.

Background tool that watches Claude Code, Codex and Cursor sessions and, once a
session has been idle for a while, rewrites its title to reflect the latest
content. Conversations drift; their titles shouldn't stay frozen on the first
message you ever sent.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("rename")
except PackageNotFoundError:  # editable install before metadata exists
    __version__ = "0.0.0+local"
