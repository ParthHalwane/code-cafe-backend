import asyncio
import json
import random
import uuid
from fastapi_app.database.mongo import db
from fastapi_app.queue.redis_connection import redis_client
from fastapi_app.queue.router import user_sse_connections
ROOM_SIZE = 2
ROOM_TYPES = ["coding", "debugging"]  # define possible challenge types

async def is_user_already_in_room(user_id: str) -> bool:
    existing = await db.rooms.find_one({
        "status": "active",
        "users.user_id": user_id
    })
    return existing is not None

async def matchmaking_loop():
    while True:
        keys = redis_client.keys("queue:*")

        for key in keys:
            decoded_key = key.decode("utf-8")
            domain = decoded_key.split(":")[1]
            length = redis_client.llen(key)
            print("Into Matchmaking ")
            while length >= ROOM_SIZE:
                users = []
                skipped_users = []

                for _ in range(length):
                    user_data = redis_client.lpop(key)
                    if not user_data:
                        continue

                    user = json.loads(user_data)

                    if await is_user_already_in_room(user["user_id"]):
                        print(f"Skipping {user['user_id']}: already in a room")
                        continue

                    users.append(user)

                    if len(users) == ROOM_SIZE:
                        break

                for user in skipped_users:
                    redis_client.rpush(key, json.dumps(user))
                print(users)
                if len(users) == ROOM_SIZE:
                    room_id = str(uuid.uuid4())
                    room = {
                        "room_id": room_id,
                        "domain": domain,
                        "room_type": random.choice(ROOM_TYPES),
                        "users": users,
                        "status": "active"
                    }
                    await db.rooms.insert_one(room)
                    print(f"Room created: {room}")
                    for user in users:
                        uid = user["user_id"]
                        if uid in user_sse_connections:
                            user_sse_connections[uid]["room_id"] = room_id
                            user_sse_connections[uid]["event"].set()
                else:
                    for user in users:
                        redis_client.rpush(key, json.dumps(user))
                    break

                length = redis_client.llen(key)


        await asyncio.sleep(10)

#         await asyncio.sleep(10000)

