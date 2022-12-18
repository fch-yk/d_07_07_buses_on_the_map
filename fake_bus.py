import json
import os
import sys

import trio
from trio_websocket import open_websocket_url


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


async def run_bus(url, bus_id, route):
    async with open_websocket_url(url) as ws:
        while True:
            for latitude, longitude in route['coordinates']:
                output_message = {
                    'busId': bus_id,
                    'lat': latitude,
                    'lng': longitude,
                    'route': bus_id
                }
                output_message = json.dumps(output_message, ensure_ascii=False)

                await ws.send_message(output_message)
                await trio.sleep(0.1)


async def main():
    directory_path = 'routes'
    url = 'ws://127.0.0.1:8080/'
    try:
        async with trio.open_nursery() as nursery:
            for route in load_routes(directory_path):
                nursery.start_soon(run_bus, url, route['name'], route)
    except OSError as ose:
        print(f'Connection attempt failed: {ose}', file=sys.stderr)

if __name__ == '__main__':
    trio.run(main)
