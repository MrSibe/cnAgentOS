from pathlib import Path
import sys

import uvicorn

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cnagentos.app import create_app  # noqa: E402


app = create_app()


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=False)


if __name__ == "__main__":
    main()
