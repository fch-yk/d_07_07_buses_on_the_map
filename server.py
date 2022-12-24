import contextlib
import functools
import json
import logging
import warnings
from dataclasses import asdict, dataclass

import trio
from trio import TrioDeprecationWarning
from trio_websocket import ConnectionClosed, serve_websocket


@dataclass
class Bus:
    busId: str  # noqa: N815
    lat: float
    lng: float
    route: str


@dataclass
class WindowBounds:
    south_lat: float
    north_lat: float
    west_lng: float
    east_lng: float

    def is_inside(self, bus):
        return (self.south_lat <= bus.lat <= self.north_lat and
                self.west_lng <= bus.lng <= self.east_lng)


logger = logging.getLogger(__file__)
buses: dict = {}


async def listen_to_bus(request):
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            message = json.loads(message)
            buses[message['busId']] = Bus(**message)
        except ConnectionClosed:
            break


async def send_buses(ws, bounds):
    buses_inside_bounds = [
        asdict(bus) for bus in buses.values() if bounds.is_inside(bus)
    ]
    logger.debug('buses inside bounds: %s', len(buses_inside_bounds))
    output_message = {
        'msgType': 'Buses',
        'buses': buses_inside_bounds
    }
    output_message = json.dumps(output_message, ensure_ascii=False)
    await ws.send_message(output_message)


async def talk_to_browser(ws, bounds):
    while True:
        try:
            await send_buses(ws, bounds)
            await trio.sleep(3)
        except ConnectionClosed:
            break


async def listen_to_browser(ws, bounds):
    while True:
        try:
            input_message = await ws.get_message()
            received_bounds = json.loads(input_message)['data']
            bounds = WindowBounds(**received_bounds)

            logger.debug(bounds)
            await send_buses(ws, bounds)
        except ConnectionClosed:
            break


async def communicate_with_browser(request):
    bounds = WindowBounds(0, 0, 0, 0)
    ws = await request.accept()
    async with trio.open_nursery() as nursery:
        # nursery.start_soon(talk_to_browser, ws, bounds)
        nursery.start_soon(listen_to_browser, ws, bounds)


async def main():
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    bus_ws_handler = functools.partial(
        serve_websocket,
        handler=listen_to_bus,
        host='127.0.0.1',
        port=8080,
        ssl_context=None
    )
    browser_ws_handler = functools.partial(
        serve_websocket,
        handler=communicate_with_browser,
        host='127.0.0.1',
        port=8000,
        ssl_context=None
    )

    async with trio.open_nursery() as nursery:
        nursery.start_soon(bus_ws_handler)
        nursery.start_soon(browser_ws_handler)


if __name__ == '__main__':
    warnings.filterwarnings(action='ignore', category=TrioDeprecationWarning)
    with contextlib.suppress(KeyboardInterrupt):
        trio.run(main)
