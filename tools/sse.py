import queue

queues = {}

def get_queue(user_id):
    if user_id not in queues:
        queues[user_id] = queue.Queue()
    return queues[user_id]

def push_event(user_id, data, event="message"):
    get_queue(user_id).put((event, data))
