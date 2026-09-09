from flask import Flask, render_template, request, jsonify
from bot_core import (
    video_id_from_url,
    get_comments,
    get_unique_channels,
    get_channel_information,
    build_domain_connections,
    build_youtube_connections,
    calculate_score,
    account_age_days,
    youtube_error_message,
    MAX_ANALYSIS_ACCOUNT_AGE_DAYS,
    MIN_SCORE,
    MAX_SCORE,
)
from googleapiclient.errors import HttpError

app = Flask(__name__)

def analyze_video(api_key, url):
    video_id = video_id_from_url(url)
    if not video_id:
        raise ValueError("That does not look like a valid YouTube video URL.")

    comments = get_comments(api_key, video_id)
    channels = get_unique_channels(comments)
    channel_ids = list(channels.keys())

    channel_infos = get_channel_information(api_key, channel_ids)

    domain_accounts = build_domain_connections(channels)
    youtube_connections = build_youtube_connections(channels, channel_infos)

    results = []

    for channel_id in channel_ids:
        channel = channels[channel_id]
        info = channel_infos.get(channel_id)
        if not info:
            continue

        age = account_age_days(info["created"])
        if age is None or age > MAX_ANALYSIS_ACCOUNT_AGE_DAYS:
            continue

        score, classification, reasons, connected, flags = calculate_score(
            channel_id,
            channel,
            info,
            domain_accounts,
            youtube_connections,
            channel_ids,
        )

        if score <= MIN_SCORE:
            continue

        age_text = "1 day" if age == 1 else f"{age} days"

        # One result per suspicious comment, matching the desktop program.
        for comment in channel["comments"]:
            results.append({
                "score": score,
                "max_score": MAX_SCORE,
                "classification": classification,
                "name": info["name"],
                "channel_id": channel_id,
                "channel_url": info["channel_url"],
                "comment": comment,
                "age": age_text,
                "connections": len(connected),
                "flags": flags,
                "reasons": reasons,
                "profile_image": channel.get("profile_image", ""),
            })

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "video_id": video_id,
        "comments": len(comments),
        "accounts": len(channel_ids),
        "hits": len(results),
        "results": results,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    url = (data.get("url") or "").strip()

    if not api_key:
        return jsonify({"error": "Please enter your YouTube API key."}), 400
    if not url:
        return jsonify({"error": "Please enter a YouTube video URL."}), 400

    try:
        result = analyze_video(api_key, url)
        return jsonify(result)
    except HttpError as exc:
        return jsonify({"error": youtube_error_message(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
