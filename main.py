import os
import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, Query
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_MESSAGE = (
    "You are a helpful and bubbly AI assistant who loves to chat about anything "
    "the user is interested in and is prepared to offer them facts. "
    "You have a penchant for dad jokes, owl jokes, and rickrolling – subtly. "
    "Always stay positive, but work in a joke when appropriate."
)
VOICE = "alloy"
LOG_EVENT_TYPES = [
    "response.content.done",
    "rate_limits.updated",
    "response.done",
    "input_audio_buffer.committed",
    "input_audio_buffer.speech_stopped",
    "input_audio_buffer.speech_started",
    "session.created",
]

app = FastAPI()
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/create-call")
async def create_call(
    to: str = Query(..., description="Phone number to make a call"),
    from_: str = Query(..., description="Phone number you purchased from Twilio"),
    stream_url: str = Query(..., description="URL to stream audio to the call"),
):
    """Creates a call and streams audio to the OpenAI Realtime API."""
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)

    call = client.calls.create(
        twiml=str(response),
        to=to,
        from_=from_,
    )

    return {"call_sid": call.sid}


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    await websocket.accept()

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        },
    ) as openai_ws:
        await send_session_update(openai_ws)
        await asyncio.gather(
            receive_from_twilio(websocket, openai_ws),
            send_to_twilio(websocket, openai_ws),
        )


async def send_session_update(openai_ws):
    """Sends session update details to OpenAI WebSocket."""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        },
    }
    print("Sending session update:", json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))


async def receive_from_twilio(websocket: WebSocket, openai_ws):
    """Receive audio data from Twilio and forward it to OpenAI Realtime API."""
    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            if data["event"] == "media" and openai_ws.open:
                audio_append = {
                    "type": "input_audio_buffer.append",
                    "audio": data["media"]["payload"],
                }
                await openai_ws.send(json.dumps(audio_append))
            elif data["event"] == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"Incoming stream started: {stream_sid}")
    except WebSocketDisconnect:
        print("Twilio client disconnected.")
        if openai_ws.open:
            await openai_ws.close()


async def send_to_twilio(websocket: WebSocket, openai_ws):
    """Receive audio responses from OpenAI and send them back to Twilio."""
    try:
        async for openai_message in openai_ws:
            response = json.loads(openai_message)
            if response["type"] in LOG_EVENT_TYPES:
                print(f"Received event: {response['type']}", response)
            elif response["type"] == "session.updated":
                print("Session updated:", response)
            elif response["type"] == "response.audio.delta" and response.get("delta"):
                try:
                    audio_payload = base64.b64encode(
                        base64.b64decode(response["delta"])
                    ).decode("utf-8")
                    audio_delta = {
                        "event": "media",
                        "streamSid": response["streamSid"],
                        "media": {"payload": audio_payload},
                    }
                    await websocket.send_json(audio_delta)
                except Exception as e:
                    print(f"Error processing audio data: {e}")
    except Exception as e:
        print(f"Error in sending data to Twilio: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0")
