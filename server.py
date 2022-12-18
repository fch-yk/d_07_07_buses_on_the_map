import functools
import json
import logging

import trio
from trio_websocket import ConnectionClosed, serve_websocket

logger = logging.getLogger(__file__)
buses = {}


async def talk_to_bus(request):
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            message = json.loads(message)
            buses[message['busId']] = message
            logger.info('from buses %s', message)
        except ConnectionClosed:
            break


async def talk_to_browser(request):
    ws = await request.accept()
    while True:
        try:
            buses_to_send = [bus for bus in buses.values()]
            output_message = {
                'msgType': 'Buses',
                'buses': buses_to_send
            }
            output_message = json.dumps(output_message, ensure_ascii=False)
            await ws.send_message(output_message)
            await trio.sleep(0.1)
        except ConnectionClosed:
            break


async def main():
    logging.basicConfig()
    logger.setLevel(logging.INFO)
    bus_ws_handler = functools.partial(
        serve_websocket,
        handler=talk_to_bus,
        host='127.0.0.1',
        port=8080,
        ssl_context=None
    )
    browser_ws_handler = functools.partial(
        serve_websocket,
        handler=talk_to_browser,
        host='127.0.0.1',
        port=8000,
        ssl_context=None
    )

    async with trio.open_nursery() as nursery:
        nursery.start_soon(bus_ws_handler)
        nursery.start_soon(browser_ws_handler)


if __name__ == '__main__':
    trio.run(main)
