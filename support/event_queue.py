import queue

# Dict that keeps tracks of who is watching and which conversation :
subscribers = {}

# To subscribe into a queue for a conversation
def subscribe(conversation_id):
    que = queue.Queue() # this will create a new empty queue where we publish events.
    if conversation_id not in subscribers:
        subscribers[conversation_id] = []

    subscribers[conversation_id].append(que)
    return que



# To unsubscribe from a queue for a conversation
def unsubscribe(conversation_id, que):

    if conversation_id in subscribers:
        subscribers[conversation_id].remove(que)

        # if the list of queue is empty then delete the empty list :
        if not subscribers[conversation_id]:
            del subscribers[conversation_id]



# To publish events to the queue
def publish(conversation_id, event):
    if conversation_id in subscribers:
        for que in subscribers[conversation_id]:
            que.put(event)

# Sentinel value - which tells SSE stream to stop
DONE = {"type": "done"}