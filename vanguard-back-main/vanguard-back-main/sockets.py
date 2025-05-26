import json
from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        self.active_connections: list = []


    async def connect(self, websocket: WebSocket, user_uuid: str, user_id: int, room: str | None, room_type: str | None):
        connection_data = {
            'user_uuid': user_uuid,
            'user_id': user_id,
            'socket': websocket
        }
        if (room): connection_data['room'] = room
        if (room_type): connection_data['room_type'] = room_type

        self.active_connections.append(connection_data)
        print(self.active_connections)



    async def disconnect(self, websocket: WebSocket):
        self.active_connections = [connection for connection in self.active_connections if connection['socket'] != websocket]
        # print(f'{websocket} disconnected.')



    async def message(self, websocket: WebSocket, event_type: str, message: dict):
        await websocket.send_json({
            'type': event_type,
            'message': message
        })


    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)



ws_manager = ConnectionManager()