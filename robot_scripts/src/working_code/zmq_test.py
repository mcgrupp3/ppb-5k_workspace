import zmq
import json
import time

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5555")

count = 0
while True:
    data = {
        "message": f"Hello {count}",
        "timestamp": time.time(),
        "count": count
    }
    socket.send_json(data)
    print(f"Sent: {data}")
    count += 1
    time.sleep(0.5)
