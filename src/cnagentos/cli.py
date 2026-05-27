import argparse
import asyncio
import getpass
import os

from cnagentos.config import get_settings
from cnagentos.db import build_engine, build_sessionmaker
from cnagentos.services.bootstrap import create_system_admin


async def create_admin(args: argparse.Namespace) -> None:
    password = os.environ.get("CNAGENTOS_BOOTSTRAP_PASSWORD") or getpass.getpass(
        "Initial administrator password: "
    )
    settings = get_settings()
    engine = build_engine(settings)
    factory = build_sessionmaker(engine)
    try:
        async with factory() as session:
            user, created = await create_system_admin(
                session, args.username, args.display_name, password
            )
            state = "created" if created else "already exists"
            print(f"System administrator {user.username} {state}.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="cnAgentOS management commands")
    commands = parser.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser("create-system-admin")
    create_parser.add_argument("--username", required=True)
    create_parser.add_argument("--display-name", required=True)
    args = parser.parse_args()
    if args.command == "create-system-admin":
        asyncio.run(create_admin(args))


if __name__ == "__main__":
    main()
