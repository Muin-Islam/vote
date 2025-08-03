from flask import Flask, render_template, request, redirect, url_for, make_response
from pymongo import MongoClient
from dotenv import load_dotenv
import time
import os

# Load .env variables
load_dotenv()

app = Flask(__name__)

# Initialize MongoDB connection at app startup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["voting_db"]
votes_col = db["votes"]

# Create indexes (only needed once)
votes_col.create_index("ip")
votes_col.create_index("timestamp")

RATE_LIMIT_SECONDS = 5

def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

@app.route("/", methods=["GET", "POST"])
def vote():
    cookie_vote_flag = request.cookies.get("voted")
    last_time = request.cookies.get("last_vote_time")

    # Rate limiting
    if request.method == "POST" and last_time and time.time() - float(last_time) < RATE_LIMIT_SECONDS:
        return "You're voting too fast. Please wait a few seconds."

    if request.method == "POST":
        if cookie_vote_flag == "yes":
            return redirect(url_for("results"))

        option = request.form.get("option")
        if option:
            ip = get_ip()
            votes_col.insert_one({
                "ip": ip,
                "option": option,
                "timestamp": int(time.time())
            })

            resp = make_response(redirect(url_for("results")))
            resp.set_cookie("voted", "yes", max_age=60*60*24)  # 1 day
            resp.set_cookie("last_vote_time", str(time.time()))
            return resp

    if request.method == "GET" and cookie_vote_flag == "yes":
        return redirect(url_for("results"))

    return render_template("vote.html")

@app.route("/results")
def results():
    try:
        results = list(votes_col.aggregate([
            {"$group": {"_id": "$option", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "option": "$_id", "count": 1}}
        ]))
        return render_template("results.html", results=results)
    except Exception as e:
        app.logger.error(f"Error fetching results: {str(e)}")
        return "Error loading results. Please try again later.", 500

@app.route("/reset")
def reset():
    resp = make_response(redirect(url_for("vote")))
    resp.set_cookie("voted", "", expires=0)
    return resp

if __name__ == "__main__":
    app.run()

