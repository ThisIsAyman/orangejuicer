"""Authentication helpers for the OrangeTheory Fitness API.

Credentials are read from environment variables ``OTF_EMAIL`` and
``OTF_PASSWORD`` (or from a ``.env`` file in the working directory).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class OTFAuth:
    """Holds OTF credentials and exposes a pre-authenticated :class:`otf_api.Otf` instance.

    Credentials are taken (in order of preference) from:

    1. Constructor arguments ``email`` / ``password``.
    2. Environment variables ``OTF_EMAIL`` / ``OTF_PASSWORD``.
    3. Interactive prompts (delegated to the underlying ``otf-api`` library).
    """

    def __init__(self, email: str | None = None, password: str | None = None) -> None:
        self.email = email or os.environ.get("OTF_EMAIL")
        self.password = password or os.environ.get("OTF_PASSWORD")

    def get_client(self):
        """Return an authenticated :class:`otf_api.Otf` instance.

        Raises
        ------
        ImportError
            If ``otf-api`` is not installed.
        RuntimeError
            If credentials are missing and the environment does not support
            interactive prompts.
        """
        try:
            from otf_api import Otf, OtfUser  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "The 'otf-api' package is required. Install it with: pip install otf-api"
            ) from exc

        if self.email and self.password:
            return Otf(user=OtfUser(self.email, self.password))

        # Fall back to interactive prompt provided by the library
        return Otf()
