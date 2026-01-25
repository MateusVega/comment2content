import time
from tools import get_comments, extract_video_id
from flask import Flask, render_template, request, url_for, Response, stream_with_context

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html", description="Play the Valorant Most Kill Team game and achieve the highest score! Test your skills and compete for the top spot.")

@app.route("/process_api", methods=["POST"])
def process_api():
    started_at = time.time()
    data = request.get_json()
    url = data.get("url")

    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL"}, 400

    comments, video_id, title, channel = get_comments(video_id, max_comments=350)

    elapsed = round(time.time() - started_at, 2)
    
    return {
        "count": len(comments),
        "comments": comments,
        "video_id": video_id,
        "title": title,
        "channel": channel,
        "time_spent" : elapsed
    }


if __name__ == "__main__":
    app.run(debug=True)
    # .\.venv\Scripts\activate