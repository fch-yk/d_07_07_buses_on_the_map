import contextlib
import functools
import json
import logging
import warnings

import trio
from trio import TrioDeprecationWarning
from trio_websocket import ConnectionClosed, serve_websocket

logger = logging.getLogger(__file__)
buses: dict = {}


def is_inside(bounds, lat, lng):
    return (bounds['south_lat'] <= lat <= bounds['north_lat'] and
            bounds['west_lng'] <= lng <= bounds['east_lng'])


async def talk_to_bus(request):
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            message = json.loads(message)
            buses[message['busId']] = message
        except ConnectionClosed:
            break


async def talk_to_browser(ws, bounds):
    while True:
        try:
            buses_to_send = [
                bus for bus in buses.values()
            ]
            buses_inside_bounds = [
                bus for bus in buses_to_send if is_inside(
                    bounds,
                    bus['lat'],
                    bus['lng']
                )
            ]
            logger.debug('%s buses inside bounds', len(buses_inside_bounds))
            output_message = {
                'msgType': 'Buses',
                'buses': buses_to_send
            }
            output_message = json.dumps(output_message, ensure_ascii=False)
            await ws.send_message(output_message)
            await trio.sleep(3)
        except ConnectionClosed:
            break


async def listen_browser(ws, bounds):
    while True:
        try:
            input_message = await ws.get_message()
            received_bounds = json.loads(input_message)['data']
            for key in received_bounds:
                bounds[key] = received_bounds[key]
            logger.debug(bounds)
        except ConnectionClosed:
            break


async def communicate_with_browser(request):
    bounds = {
        'south_lat': 0,
        'north_lat': 0,
        'west_lng': 0,
        'east_lng': 0,
    }
    ws = await request.accept()
    async with trio.open_nursery() as nursery:
        nursery.start_soon(talk_to_browser, ws, bounds)
        nursery.start_soon(listen_browser, ws, bounds)


async def main():
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    bus_ws_handler = functools.partial(
        serve_websocket,
        handler=talk_to_bus,
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
