import os
import time
import json
import ollama
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()
cwd = os.getcwd()
CACHE_TTL = 48 * 3600

# __________________________________________________________________ #
# Youtube Api

api_key = os.getenv("YOUTUBE_API_KEY")
if not api_key:
    raise RuntimeError("YOUTUBE_API_KEY not defined.")

youtube = build("youtube", "v3", developerKey=api_key)

# Fetch Comments

def fetch_comments(video_id, max_comments=200):
    comments = []
    next_page_token = None

    try:
        while len(comments) < max_comments:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_comments - len(comments)),
                pageToken=next_page_token,
                order="relevance",
                textFormat="plainText"
            )

            response = request.execute()

            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "text": snippet["textDisplay"],
                    "likes": snippet.get("likeCount", 0),
                    "published_at": snippet.get("publishedAt"),
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except HttpError as e:
        print(f"YouTube API error: {e}")
        return []

    return comments, len(comments)

def fetch_video_info(video_id):
    request = youtube.videos().list(
        part="snippet",
        id=video_id,
    )

    response = request.execute()

    if not response["items"]:
        return {"error": "Invalid YouTube URL"}, 400

    snippet = response["items"][0]["snippet"]
    title = snippet["title"]
    channel = snippet["channelTitle"]

    return title, channel

def extract_video_id(url):
    try:
        parsed = urlparse(url)

        # youtu.be/<id>
        if parsed.netloc in ("youtu.be", "www.youtu.be"):
            return parsed.path.lstrip("/")

        # youtube.com/watch?v=<id>
        if "youtube.com" in parsed.netloc:
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [None])[0]

            # youtube.com/shorts/<id>
            if parsed.path.startswith("/shorts/"):
                return parsed.path.split("/shorts/")[1]
    except Exception:
        return None
    return None

# Filter Comments

def remove_noise(comments):
    clean = []

    for c in comments:
        text = c["text"].lower().strip()

        if len(text) < 15:
            continue

        clean.append(c)

    return clean

    suggestions = []
    grouped_ideas = []

    for i in range(0, len(comments), batch_size):
        batch = comments[i:i + batch_size]
        texts = [c["text"] for c in batch]

        result = llm_classify_batch(texts)

        # collect filtered comments
    for idx in result.get("suggestions", []):
        if 0 <= idx < len(batch):
            suggestions.append(batch[idx])

        grouped_ideas.extend(result.get("grouped_ideas", []))

    return suggestions, grouped_ideas

def llm_is_recommendation(comment):
    prompt = f"""
        Classify the comment.

        Return True ONLY if it requests or suggests specific future content
        (e.g. "make a video about X", "cover Y", "do a series on Z").
        The request must include:
        - a clear topic, format, collaboration, or continuation
        - at least one concrete detail (topic, person, skill, or concept)
        Praise, opinions, or hype without a specific topic → False.
        Any language allowed.

        Answer ONLY with:
        True
        or
        False

        Comment: "{comment}"
    """


    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0}
    )

    return response["message"]["content"].strip().lower().startswith("true")

def llm_classify_parallel(comments, workers=4):
    results = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(llm_is_recommendation, c["text"]): c
            for c in comments
        }

        for future in as_completed(futures):
            if future.result():
                results.append(futures[future])

    return results

def filter_comments(comments):
    comments = sorted(comments, key=lambda c: c["likes"], reverse=True)
    comments = remove_noise(comments)
    filtered_comments = llm_classify_parallel(comments)
    return filtered_comments

# Cache Comments

def caching_comments_with_json(video_id, comments, total_comments_fetched):
    cache_comments = {
        "cached_at" : time.time(),
        "total_comments_fetched" : total_comments_fetched,
        "data" : comments
    }

    with open(os.path.join(cwd, "static", "videos_cache", f"{video_id}.json"), 'w') as json_file:
        json.dump(cache_comments, json_file, indent=4)

def video_cached(video_id):
    videos_cache_path = os.path.join(cwd, "static", "videos_cache")
    if f"{video_id}.json" in os.listdir(videos_cache_path):
        return True
    return False

def get_cached_video(video_id):
    path = os.path.join(cwd, "static", "videos_cache", f"{video_id}.json")
    if not os.path.exists(path):
        return None, None

    with open(path, "r") as f:
        payload = json.load(f)

    if time.time() - payload["cached_at"] > CACHE_TTL:
        os.remove(path)
        return None, None

    return payload["data"], payload["total_comments_fetched"]

# Main function

def get_comments(video_id, max_comments):
    title, channel = fetch_video_info(video_id)

    cached, total_comments_fetched = get_cached_video(video_id)
    if cached is not None:
        return cached, video_id, title, channel, total_comments_fetched

    raw_comments, total_comments_fetched = fetch_comments(video_id, max_comments=max_comments)
    result = filter_comments(raw_comments)
    caching_comments_with_json(video_id, result, total_comments_fetched)

    return result, video_id, title, channel, total_comments_fetched