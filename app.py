from datetime import date, timedelta
import uuid
import os
from dotenv import load_dotenv
import time
from tools.tools import get_comments, extract_video_id
from tools.sse import get_queue, push_event
from flask import Flask, render_template, request, url_for, session, Response

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY_SK")
app.permanent_session_lifetime = timedelta(days=1)

user_id = None

def event_stream(user_id):
    q = get_queue(user_id)
    while True:
        event, data = q.get()
        yield f"event: {event}\ndata: {data}\n\n"

@app.route("/stream")
def sse_route():
    return Response(
        event_stream(session["user_id"]),
        mimetype="text/event-stream"
    )

app.add_url_rule("/stream", view_func=sse_route)

@app.route("/")
def index():
    global user_id
    if not session.get('user_id'):
        session['user_id'] = str(uuid.uuid4())
        user_id = session['user_id']
    return render_template("index.html", description="Play the Valorant Most Kill Team game and achieve the highest score! Test your skills and compete for the top spot.")

@app.route("/process_api", methods=["POST"])
def process_api():
    global user_id
    started_at = time.time()
    data = request.get_json()
    url = data.get("url")

    push_event(user_id, 5, event="status")

    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL"}, 400

    session.permanent = True
    today = date.today().isoformat()
    
    if session.get("day") != today:
        session["day"] = today
        session["count"] = 0

    session["count"] = 0
    session["count"] += 1

    if session["count"] > 3:
        return {"error": "You can analyze up to 3 videos per day. Try again tomorrow"}, 429
    
    comments, video_id, title, channel, total_comments_fetched = get_comments(video_id, max_comments=250)

    elapsed = round(time.time() - started_at, 2)

    return {
        "count": len(comments),
        "comments": comments,
        "video_id": video_id,
        "title": title,
        "channel": channel,
        "time_spent": elapsed,
        "total_comments_fetched": total_comments_fetched
    }

if __name__ == "__main__":
    app.run(debug=True)
    # .\.venv\Scripts\activate