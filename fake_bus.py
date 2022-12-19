import json
import os
import random
import sys
import itertools

import trio
from trio_websocket import open_websocket_url


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


def generate_bus_id(route_id, bus_index):
    return f"{route_id}-{bus_index}"


async def run_bus(url, bus_id, route_name, coordinates):
    async with open_websocket_url(url) as ws:
        while True:
            for latitude, longitude in coordinates:
                output_message = {
                    'busId': bus_id,
                    'lat': latitude,
                    'lng': longitude,
                    'route': route_name
                }
                output_message = json.dumps(output_message, ensure_ascii=False)

                await ws.send_message(output_message)
                await trio.sleep(0.1)


async def main():
    directory_path = 'routes'
    url = 'ws://127.0.0.1:8080/'
    min_per_route = 3
    max_per_route = 10
    try:
        async with trio.open_nursery() as nursery:
            for route in load_routes(directory_path):
                basic_coordinates = route['coordinates']
                per_route = random.randint(min_per_route, max_per_route)
                for bus_index in range(per_route):
                    bus_id = generate_bus_id(route['name'], bus_index)
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
                        url,
                        bus_id,
                        route['name'],
                        coordinates
                    )
    except OSError as ose:
        print(f'Connection attempt failed: {ose}', file=sys.stderr)

if __name__ == '__main__':
    trio.run(main)
