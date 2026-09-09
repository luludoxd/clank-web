from flask import Flask, render_template, request, jsonify
from bot_core import (
    video_id_from_url, get_comments, get_unique_channels,
    get_channel_information, build_domain_connections,
    build_youtube_connections, calculate_score, account_age_days,
    MAX_ANALYSIS_ACCOUNT_AGE_DAYS, MIN_SCORE, MAX_SCORE
)
from googleapiclient.errors import HttpError

app=Flask(__name__)

def youtube_error_message(error):
    text=str(error); status=getattr(getattr(error,"resp",None),"status",None)
    if status==403 and "quota" in text.lower(): return "YouTube API quota exceeded. Try again later or use another API key."
    if status==403: return "YouTube rejected the API request. Check the API key and that YouTube Data API v3 is enabled."
    if status==400: return "YouTube rejected the request. Check the video URL."
    if status==404: return "YouTube could not find that video."
    return text

def analyze_video(api_key,url):
    video_id=video_id_from_url(url)
    if not video_id: raise ValueError("That does not look like a valid YouTube video URL.")
    comments=get_comments(api_key,video_id)
    channels=get_unique_channels(comments)
    channel_ids=list(channels.keys())
    infos=get_channel_information(api_key,channel_ids)
    domain_accounts=build_domain_connections(channels)
    youtube_connections=build_youtube_connections(channels,infos)
    results=[]
    for cid in channel_ids:
        ch=channels[cid]; info=infos.get(cid)
        if not info: continue
        age=account_age_days(info["created"])
        if age is None or age>MAX_ANALYSIS_ACCOUNT_AGE_DAYS: continue
        score,classification,reasons,connected,flags=calculate_score(
            cid,ch,info,domain_accounts,youtube_connections,channel_ids)
        if score<=MIN_SCORE: continue
        for comment in ch["comments"]:
            results.append({"score":score,"max_score":MAX_SCORE,
                "classification":classification,"name":info["name"],
                "channel_url":info["channel_url"],"comment":comment,
                "age":"1 day" if age==1 else f"{age} days",
                "connections":len(connected),"flags":flags,"reasons":reasons})
    results.sort(key=lambda x:x["score"],reverse=True)
    return {"video_id":video_id,"comments":len(comments),
            "accounts":len(channel_ids),"hits":len(results),"results":results}

@app.get("/")
def index(): return render_template("index.html")

@app.post("/api/analyze")
def analyze():
    data=request.get_json(silent=True) or {}
    key=(data.get("api_key") or "").strip(); url=(data.get("url") or "").strip()
    if not key: return jsonify(error="Please enter your YouTube API key."),400
    if not url: return jsonify(error="Please enter a YouTube video URL."),400
    try: return jsonify(analyze_video(key,url))
    except HttpError as e: return jsonify(error=youtube_error_message(e)),400
    except Exception as e: return jsonify(error=str(e)),400

if __name__=="__main__": app.run(host="0.0.0.0",port=5000)
