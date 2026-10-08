"""Expose a host-only HTTP proxy to local Docker containers through docker0.

This is a development-network workaround. Bind only to the Docker bridge gateway;
never expose this relay on a public interface.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress


async def _relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def _serve(bind: str, listen_port: int, upstream_host: str, upstream_port: int) -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream_host, upstream_port
            )
        except OSError:
            writer.close()
            await writer.wait_closed()
            return
        await asyncio.gather(
            _relay(reader, upstream_writer),
            _relay(upstream_reader, writer),
        )

    server = await asyncio.start_server(handle, bind, listen_port)
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="172.17.0.1")
    parser.add_argument("--port", type=int, default=17897)
    parser.add_argument("--upstream-host", default="127.0.0.1")
    parser.add_argument("--upstream-port", type=int, default=7897)
    args = parser.parse_args()
    address = ipaddress.ip_address(args.bind)
    if not address.is_private or address.is_loopback or address.is_unspecified:
        parser.error("--bind must be a private Docker bridge address")
    asyncio.run(_serve(args.bind, args.port, args.upstream_host, args.upstream_port))


if __name__ == "__main__":
    main()
