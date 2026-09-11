from flask import Flask, render_template, request, jsonify
from bot_core import (
    video_id_from_url, get_comments, get_unique_channels,
    get_channel_information, build_domain_connections,
    build_youtube_connections, calculate_score, account_age_days,
    create_report_text, MIN_SCORE, MAX_SCORE,
    MAX_ANALYSIS_ACCOUNT_AGE_DAYS
)
from googleapiclient.errors import HttpError

app = Flask(__name__)

def api_error(exc):
    status = getattr(getattr(exc, "resp", None), "status", None)
    text = str(exc)
    if status == 403 and "quota" in text.lower():
        return "YouTube API quota exceeded. Wait for the quota reset or use another API key."
    if status == 403:
        return "YouTube rejected the API request. Check the API key and make sure YouTube Data API v3 is enabled."
    if status == 400:
        return "YouTube rejected the request. Check the video URL."
    if status == 404:
        return "YouTube could not find that video."
    return text

def analyze(api_key, url, ignored_ids=None):
    video_id = video_id_from_url(url)
    if not video_id:
        raise ValueError("No valid YouTube video ID was found.")

    comments = get_comments(video_id, api_key=api_key)
    channels = get_unique_channels(comments)
    ignored_ids = set(ignored_ids or [])
    for cid in ignored_ids:
        channels.pop(cid, None)

    ids = list(channels.keys())
    infos = get_channel_information(ids, api_key=api_key)
    domains = build_domain_connections(channels)
    yt_connections = build_youtube_connections(channels, infos)

    results = []
    for cid in ids:
        info = infos.get(cid)
        channel = channels[cid]
        if not info:
            continue
        age = account_age_days(info.get("created"))
        if age is None or age > MAX_ANALYSIS_ACCOUNT_AGE_DAYS:
            continue

        score, classification, reasons, connected, flags = calculate_score(
            cid, channel, info, domains, yt_connections, ids
        )
        if score <= MIN_SCORE:
            continue

        for comment in channel.get("comments", []):
            item = {
                "score": score, "max_score": MAX_SCORE,
                "classification": classification,
                "name": info.get("name", "Unknown"),
                "channel_id": cid,
                "channel_url": info.get("channel_url"),
                "comment": comment,
                "age": f"{age} days" if age != 1 else "1 day",
                "connections": len(connected),
                "flags": flags, "reasons": reasons,
                "profile_image": channel.get("profile_image", "")
            }
            item["report"] = create_report_text(item, profile_image=False)
            item["profile_report"] = create_report_text(item, profile_image=True)
            results.append(item)

    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "video_id": video_id,
        "comments": len(comments),
        "accounts": len(ids),
        "hits": len(results),
        "results": results
    }

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/analyze")
def analyze_route():
    data = request.get_json(silent=True) or {}
    key = (data.get("api_key") or "").strip()
    url = (data.get("url") or "").strip()
    ignored = data.get("ignored_ids") or []
    if not key:
        return jsonify({"error": "No YouTube API key configured."}), 400
    if not url:
        return jsonify({"error": "Enter a YouTube video or Short URL."}), 400
    try:
        return jsonify(analyze(key, url, ignored))
    except HttpError as exc:
        return jsonify({"error": api_error(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

@app.post("/api/library-status")
def library_status():
    data = request.get_json(silent=True) or {}
    key = (data.get("api_key") or "").strip()
    ids = list(dict.fromkeys(data.get("ids") or []))
    if not key:
        return jsonify({"error": "No API key."}), 400
    try:
        from bot_core import get_youtube_service
        service = get_youtube_service(key)
        found = {}
        for start in range(0, len(ids), 50):
            batch = ids[start:start+50]
            if not batch:
                continue
            response = service.channels().list(
                part="snippet,statistics", id=",".join(batch)
            ).execute()
            found.update({x["id"]: x for x in response.get("items", [])})
        return jsonify({"online": list(found.keys())})
    except HttpError as exc:
        return jsonify({"error": api_error(exc)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
