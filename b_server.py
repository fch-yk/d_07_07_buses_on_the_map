import json

import trio
from trio_websocket import ConnectionClosed, serve_websocket


async def echo_server(request):
    ws = await request.accept()
    route_path = 'routes/156.json'
    route = ''
    async with await trio.open_file(
        route_path,
        mode='r',
        encoding='UTF-8'
    ) as file:
        async for line in file:
            route += line
    route = json.loads(route)
    route_name = route['name']
    bus_id = 'c790сс'
    while True:
        try:
            for latitude, longitude in route['coordinates']:
                output_message = {
                    'msgType': 'Buses',
                    'buses': [
                        {
                            'busId': bus_id, 'lat': latitude,
                            'lng': longitude, 'route': route_name,
                        },
                    ]
                }
                output_message = json.dumps(output_message)
                await ws.send_message(output_message)
                await trio.sleep(1)
        except ConnectionClosed:
            break


async def main():
    await serve_websocket(echo_server, '127.0.0.1', 8000, ssl_context=None)

if __name__ == '__main__':
    trio.run(main)
