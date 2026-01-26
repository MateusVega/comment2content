import queue

event_queue = queue.Queue()

def push_event(data, event="message"):
    event_queue.put((event, data))