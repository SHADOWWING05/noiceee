from flask import Flask, request, jsonify, render_template
import os
import requests
import google.generativeai as genai
import jwt
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# === CONFIG ===
GOOGLE_API_KEY = "AIzaSyBBGpIDxjhGm_kmd1-t40BLb9RXyBUcQ5M" 
ASSEMBLYAI_API_KEY ="74dc644d47c24c70802b1c0c0fa7a8d4" 

LIVEKIT_API_KEY = "APIXhjc36VzyufX"
LIVEKIT_API_SECRET = "y0upP1Lt6sAJJ3lVSM1hjBbfVXPUibeFHJgiWzndM1e"
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://your-livekit-domain/livekit")

# === Configure Gemini ===
genai.configure(api_key=GOOGLE_API_KEY)

def generate_gemini_reply(prompt):
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

@app.route('/')
def index():
    return render_template("index.html", livekit_url=LIVEKIT_URL)

@app.route('/token', methods=['GET'])
def get_token():
    identity = request.args.get("identity", f"user-{int(time.time())}")
    room = request.args.get("room", "default")

    payload = {
        "jti": f"{identity}-{int(time.time())}",
        "iss": LIVEKIT_API_KEY,
        "sub": identity,
        "nbf": int(time.time()),
        "exp": int(time.time()) + 3600,
        "video": True,
        "audio": True,
        "room": room,
        "roomJoin": True,
        "canPublish": True,
        "canSubscribe": True
    }

    token = jwt.encode(payload, LIVEKIT_API_SECRET, algorithm="HS256")
    return jsonify({
        "identity": identity,
        "token": token
    })

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio uploaded'}), 400

    audio_file = request.files['audio']

    # Upload to AssemblyAI
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/octet-stream"
    }

    upload_url = "https://api.assemblyai.com/v2/upload"
    upload_response = requests.post(upload_url, headers=headers, data=audio_file)

    if upload_response.status_code != 200:
        return jsonify({"error": "Failed to upload audio"}), 500

    audio_url = upload_response.json()['upload_url']

    transcript_req = {
        "audio_url": audio_url,
        "language_code": "en_us"
    }

    transcript_response = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        json=transcript_req,
        headers={"authorization": ASSEMBLYAI_API_KEY}
    )

    transcript_id = transcript_response.json()["id"]
    status_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"

    # Poll until done
    while True:
        status_check = requests.get(status_url, headers={"authorization": ASSEMBLYAI_API_KEY}).json()
        if status_check["status"] == "completed":
            text = status_check["text"]
            reply = generate_gemini_reply(text)
            return jsonify({"transcript": text, "reply": reply})
        elif status_check["status"] == "error":
            return jsonify({"error": status_check.get("error", "Unknown error")}), 500

if __name__ == '__main__':
    app.run(debug=True)
