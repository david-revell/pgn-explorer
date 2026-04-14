from __future__ import annotations

import os

os.environ["PGN_EXPLORER_MODE"] = "public"
os.environ["PGN_EXPLORER_ALLOW_PGN_WRITES"] = "0"

from app import main


if __name__ == "__main__":
    main()
