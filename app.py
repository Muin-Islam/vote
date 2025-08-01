from flask import Flask, render_template, request, redirect, url_for, make_response
from pymongo import MongoClient
from dotenv import load_dotenv
import time
import os

# Load .env variables
load_dotenv()

app = Flask(__name__)

# Use environment variable
client = MongoClient(os.getenv("MONGO_URI"))
db = client["voting_db"]
votes_col = db["votes"]

RATE_LIMIT_SECONDS = 5

def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

@app.route("/", methods=["GET", "POST"])
def vote():
    cookie_vote_flag = request.cookies.get("voted")
    last_time = request.cookies.get("last_vote_time")

    # Rate limiting (based on last cookie timestamp)
    if last_time and time.time() - float(last_time) < RATE_LIMIT_SECONDS:
        return "You're voting too fast. Please wait a few seconds."

    if request.method == "POST":
        if cookie_vote_flag == "yes":
            return redirect(url_for("results"))

        option = request.form.get("option")
        if option:
            # Store IP and timestamp for logging/stats
            ip = get_ip()
            votes_col.insert_one({
                "ip": ip,
                "option": option,
                "timestamp": int(time.time())
            })

            # Set cookies to prevent multiple votes
            resp = make_response(redirect(url_for("results")))
            resp.set_cookie("voted", "yes", max_age=60*60*24*7)  # 7 days
            resp.set_cookie("last_vote_time", str(time.time()))
            return resp

    if cookie_vote_flag == "yes":
        return redirect(url_for("results"))

    return render_template("vote.html")

@app.route("/results")
def results():
    pipeline = [
        {"$group": {"_id": "$option", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "option": "$_id", "count": 1}}
    ]
    results = list(votes_col.aggregate(pipeline))
    return render_template("results.html", results=results)


if __name__ == "__main__":
    app.run()
