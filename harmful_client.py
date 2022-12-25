import contextlib
import itertools
import json
import logging

import trio
from trio_websocket import open_websocket_url


async def main():
    output_messages = (
        'Not a JSON string',
        json.dumps('Incorrect type'),
        json.dumps({'invalid_key': 'invalid key'}),
        json.dumps({'msgType': 'invalid msgType'}),
    )
    async with open_websocket_url('ws://127.0.0.1:8000/') as ws:
        for output_message in itertools.cycle(output_messages):
            try:
                await ws.send_message(output_message)
                message = await ws.get_message()
                logging.warning('Received message: %s', message)
            except OSError as ose:
                logging.error('Connection attempt failed: %s', ose)

if __name__ == '__main__':
    with contextlib.suppress(KeyboardInterrupt):
        trio.run(main)
