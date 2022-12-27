import contextlib
import functools
import itertools
import json
import logging
import os
import random
import sys
import uuid
import warnings
from dataclasses import asdict

import asyncclick as click
import trio
import trio_websocket
from trio import TrioDeprecationWarning

from server import Bus

logger = logging.getLogger(__file__)


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


def generate_bus_id(route_id, bus_index, emulator_id):
    return f"{emulator_id}-{route_id}-{bus_index}"


def reconnect(connect_func):
    @functools.wraps(connect_func)
    async def wrap(*args, **kwargs):
        while True:
            try:
                await connect_func(*args, **kwargs)
            except (
                trio_websocket._impl.HandshakeError,
                trio_websocket._impl.ConnectionClosed,
            ):
                logger.debug(
                    'Failed to connect to the server. Reconnecting...')
                await trio.sleep(3)
    return wrap


@reconnect
async def send_updates(server, receive_channel):
    async with trio_websocket.open_websocket_url(server) as ws:
        logger.debug('Connected to the server. Sending messages...')
        async for output_message in receive_channel:
            await ws.send_message(output_message)


async def run_bus(
    send_channel,
    bus_id,
    route_name,
    coordinates,
    refresh_timeout
):
    while True:
        for latitude, longitude in coordinates:
            bus = Bus(bus_id, latitude, longitude, route_name)
            output_message = json.dumps(asdict(bus), ensure_ascii=False)

            await send_channel.send(output_message)
            await trio.sleep(refresh_timeout)


async def fake_buses(
    server,
    routes_number,
    buses_per_route,
    websockets_number,
    emulator_id,
    refresh_timeout,
    routes_path
):
    websockets = []
    try:
        async with trio.open_nursery() as nursery:
            for _ in range(websockets_number):
                websockets.append(trio.open_memory_channel(0))

            for _, receive_channel in websockets:
                nursery.start_soon(
                    send_updates,
                    server,
                    receive_channel
                )

            for run_routes_number, route in enumerate(
                load_routes(routes_path),
                start=1
            ):
                basic_coordinates = route['coordinates']

                for bus_index in range(buses_per_route):
                    bus_id = generate_bus_id(
                        route['name'],
                        bus_index,
                        emulator_id
                    )
                    start_location = random.randint(
                        0,
                        len(basic_coordinates) - 1
                    )
                    coordinates = itertools.cycle(
                        basic_coordinates[start_location::] +
                        basic_coordinates[:start_location]
                    )

                    nursery.start_soon(
                        run_bus,
                        random.choice(websockets)[0],
                        bus_id,
                        route['name'],
                        coordinates,
                        refresh_timeout,
                    )
                logger.debug(f'Run route: {route["name"]}')
                if routes_number and run_routes_number == routes_number:
                    break
            logger.debug(f'Run routes number: {run_routes_number}')
    except OSError as ose:
        print(f'Connection attempt failed: {ose}', file=sys.stderr)


@click.command()
@click.option(
    '-s',
    '--server',
    default='ws://127.0.0.1:8080/',
    help='Server address, default: ws://127.0.0.1:8080/'
)
@click.option(
    '-rn',
    '--routes_number',
    type=click.INT,
    default=0,
    help='Number of routes, default: all (zero also means all)'
)
@click.option(
    '-bpr',
    '--buses_per_route',
    type=click.INT,
    default=5,
    help='Number of buses per route, default: 5'
)
@click.option(
    '-wn',
    '--websockets_number',
    type=click.INT,
    default=5,
    help='Number of opened websockets, default: 5'
)
@click.option(
    '-eid',
    '--emulator_id',
    default=uuid.uuid4(),
    help='Emulator ID (it is used as a prefix for bus IDs in order to support '
    'running multiple instances of the script, default: a random UUID)'
)
@click.option(
    '-rt',
    '--refresh_timeout',
    type=click.FLOAT,
    default=1,
    help='Refresh timeout, default: 1'
)
@click.option(
    '-v/-nov',
    '--verbose/--no_verbose',
    default=False,
    help='Verbose mode (logging), default: off'
)
@click.option(
    '-rp',
    '--routes_path',
    default='routes',
    help='A path to the folder containing JSON files of routes, default: routes'
)
async def main(
    server,
    routes_number,
    buses_per_route,
    websockets_number,
    emulator_id,
    refresh_timeout,
    verbose,
    routes_path
):
    '''This script fakes buses'''
    if verbose:
        logging.basicConfig()
        logger.setLevel(logging.DEBUG)
    with contextlib.suppress(KeyboardInterrupt):
        await fake_buses(
            server,
            routes_number,
            buses_per_route,
            websockets_number,
            emulator_id,
            refresh_timeout,
            routes_path,
        )


if __name__ == '__main__':
    warnings.filterwarnings(action='ignore', category=TrioDeprecationWarning)
    main(_anyio_backend="trio")
