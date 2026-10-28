#!/usr/bin/env python3

import asyncio
import json

from websockets.asyncio.client import connect


URL = "ws://127.0.0.1:8765"


async def main():

    print(
        "[CLIENT] connexion à",
        URL,
    )

    async with connect(
        URL
    ) as websocket:

        print(
            "[CLIENT] connecté ✅"
        )

        async for message in websocket:

            data = json.loads(
                message
            )

            print()
            print(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass
