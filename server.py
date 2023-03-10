import contextlib
import functools
import json
import logging
import warnings
from dataclasses import asdict, dataclass

import asyncclick as click
import trio
from trio import TrioDeprecationWarning
from trio_websocket import ConnectionClosed, serve_websocket

logger = logging.getLogger(__file__)
buses: dict = {}


@dataclass
class Bus:
    busId: str  # noqa: N815
    lat: float
    lng: float
    route: str

    @staticmethod
    def validate(message):
        bus_card = json.loads(message)
        errors = ['Requires busId specified']
        if not isinstance(bus_card, dict):
            return None, errors

        bus_id = bus_card.get('busId')
        if not bus_id:
            return None, errors

        return bus_card, None


@dataclass
class WindowBounds:
    south_lat: float = 0
    north_lat: float = 0
    west_lng: float = 0
    east_lng: float = 0
    errors: None = None

    def is_inside(self, bus):
        return (self.south_lat <= bus.lat <= self.north_lat and
                self.west_lng <= bus.lng <= self.east_lng)

    def update(self, south_lat, north_lat, west_lng, east_lng):
        self.south_lat = south_lat
        self.north_lat = north_lat
        self.west_lng = west_lng
        self.east_lng = east_lng

    def validate(self, message):
        message_card = json.loads(message)
        errors = ['Requires msgType specified']
        if not isinstance(message_card, dict):
            self.errors = errors
            return None

        msg_type = message_card.get('msgType')
        if not msg_type == 'newBounds':
            self.errors = errors

        return message_card

    def set_invalid_json_error(self):
        self.errors = ['Requires valid JSON']


async def send_errors_message(ws, errors):
    output_message = {'errors': errors, 'msgType': 'Errors'}
    output_message = json.dumps(output_message, ensure_ascii=False)
    await ws.send_message(output_message)


async def communicate_with_bus(request):
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            bus_card, errors = Bus.validate(message)
            if errors:
                await trio.sleep(3)
                await send_errors_message(ws, errors)
                continue

            buses[bus_card['busId']] = Bus(**bus_card)
        except ConnectionClosed:
            break
        except json.decoder.JSONDecodeError:
            await send_errors_message(ws, ['Requires valid JSON'])


async def send_buses(ws, bounds):
    if bounds.errors:
        await send_errors_message(ws, bounds.errors)
        return

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


async def talk_to_browser(ws, bounds, refresh_timeout):
    while True:
        try:
            await send_buses(ws, bounds)
            await trio.sleep(refresh_timeout)
        except ConnectionClosed:
            break


async def listen_to_browser(ws, bounds: WindowBounds):
    '''
    Receives bounds of the window from a browser.
    Modifies "bounds" argument in order to pass it to "talk_to_browser"
    function
    '''
    while True:
        try:
            input_message = await ws.get_message()
            message_card = bounds.validate(input_message)
            if bounds.errors:
                continue
            received_bounds = message_card['data']
            bounds.update(
                received_bounds['south_lat'],
                received_bounds['north_lat'],
                received_bounds['west_lng'],
                received_bounds['east_lng'],
            )

            logger.debug(bounds)
        except ConnectionClosed:
            break
        except json.decoder.JSONDecodeError:
            bounds.set_invalid_json_error()


async def communicate_with_browser(request, refresh_timeout):
    bounds = WindowBounds()
    ws = await request.accept()
    async with trio.open_nursery() as nursery:
        nursery.start_soon(listen_to_browser, ws, bounds)
        nursery.start_soon(talk_to_browser, ws, bounds, refresh_timeout)


@click.command()
@click.option(
    '-s',
    '--server',
    default='127.0.0.1',
    help='Server address, default: 127.0.0.1'
)
@click.option(
    '-bup',
    '--bus_port',
    type=click.INT,
    default=8080,
    help='Bus port, default: 8080'
)
@click.option(
    '-brp',
    '--browser_port',
    type=click.INT,
    default=8000,
    help='Browser port, default: 8000'
)
@click.option(
    '-v/-nov',
    '--verbose/--no_verbose',
    default=False,
    help='Verbose mode (logging), default: off'
)
@click.option(
    '-rt',
    '--refresh_timeout',
    type=click.FLOAT,
    default=1,
    help='Refresh timeout, default: 1'
)
async def main(server, bus_port, browser_port, verbose, refresh_timeout):
    '''This script serves movement of buses on the map'''
    if verbose:
        logging.basicConfig()
        logger.setLevel(logging.DEBUG)

    bus_ws_handler = functools.partial(
        serve_websocket,
        handler=communicate_with_bus,
        host=server,
        port=bus_port,
        ssl_context=None
    )
    communicate_with_browser_handler = functools.partial(
        communicate_with_browser,
        refresh_timeout=refresh_timeout
    )
    browser_ws_handler = functools.partial(
        serve_websocket,
        handler=communicate_with_browser_handler,
        host=server,
        port=browser_port,
        ssl_context=None
    )

    async with trio.open_nursery() as nursery:
        nursery.start_soon(bus_ws_handler)
        nursery.start_soon(browser_ws_handler)


if __name__ == '__main__':
    warnings.filterwarnings(action='ignore', category=TrioDeprecationWarning)
    with contextlib.suppress(KeyboardInterrupt):
        main(_anyio_backend="trio")
