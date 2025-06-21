from flask import Flask, render_template, request, jsonify
import jwt
import time
import google.generativeai as genai

# === CONFIGURATION ===
LIVEKIT_URL = "wss://myfirstprojuect-p3uw7evd.livekit.cloud"
API_KEY = "APIXhjc36VzyufX"
API_SECRET = "y0upP1Lt6sAJJ3lVSM1hjBbfVXPUibeFHJgiWzndM1e"
GEMINI_API_KEY = "AIzaSyDQNS0rFb3dSNSxvYzNswF1MJ6BzVBkpWo"

app = Flask(__name__)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-pro")

# === ROUTES ===

@app.route("/")
def index():
    return render_template("index.html", livekit_url=LIVEKIT_URL, api_key=API_KEY)

@app.route("/get_token", methods=["POST"])
def get_token():
    identity = request.json.get("identity", "user")
    ttl = 3600
    payload = {
        "iss": API_KEY,
        "sub": API_KEY,
        "nbf": int(time.time()),
        "exp": int(time.time()) + ttl,
        "video": {"roomJoin": True, "room": "*"},
        "name": identity,
        "identity": identity,
    }
    token = jwt.encode(payload, API_SECRET, algorithm="HS256")
    return jsonify({"token": token})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    context = data.get("context", "")
    user_message = data.get("message", "")
    prompt = context.strip() + "\n\nUser: " + user_message + "\nAI:"

    try:
        response = gemini_model.generate_content(prompt)
        return jsonify({"response": response.text.strip()})
    except Exception as e:
        return jsonify({"response": f"Error: {e}"})


app = Flask(__name__)

@app.route("/")
def home():
    return "Hello from Flask!"

if __name__ == "__main__":
    app.run(debug=True)
