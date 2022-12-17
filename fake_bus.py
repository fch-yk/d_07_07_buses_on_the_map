import json
import sys

import trio
from trio_websocket import open_websocket_url


async def load_route(route_path):
    route = ''
    async with await trio.open_file(
        route_path,
        mode='r',
        encoding='UTF-8'
    ) as file:
        async for line in file:
            route += line
    return json.loads(route)


async def main():
    route_path = 'routes/156.json'
    route = await load_route(route_path)

    route_name = route['name']
    bus_id = 'c790сс'
    try:
        async with open_websocket_url('ws://127.0.0.1:8080/') as ws:
            for latitude, longitude in route['coordinates']:
                output_message = {
                    'busId': bus_id,
                    'lat': latitude,
                    'lng': longitude,
                    'route': route_name
                }
                output_message = json.dumps(output_message, ensure_ascii=False)

                await ws.send_message(output_message)
                await trio.sleep(1)

    except OSError as ose:
        print(f'Connection attempt failed: {ose}', file=sys.stderr)

if __name__ == '__main__':
    trio.run(main)
