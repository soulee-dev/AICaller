# AICaller
Make outbound call with ChatGPT Realtime API.

## Prerequisites
- Twilio
  - Twilio number with **Voice** capabilities ([Here are instructions](https://help.twilio.com/articles/223135247-How-to-Search-for-and-Buy-a-Twilio-Phone-Number-from-Console) to purchase a phone number)
  - API key
- OpenAI
  - API Key (You can signup [here](https://platform.openai.com/playground))

## Setup
### Update the .env
Rename `.env.example` into `.env` and type the credentials for Twilio and OpenAI.

### Run
**Highly recommend to use virtual env to run this project.**

```bash
git clone https://github.com/soulee-dev/AICaller
pip install -r requirements.txt
python main.py
```

### Open an ngrok tunnel
Copy `Forwarding` URL. It will look something like: `https://[ngrok-subdomain].ngrok.app`

### Test the app
[http://localhost:8000/docs](https://localhost:8000/docs)
1. Access to interactive docs
2. Choose `create-call` endpoint
3. Fill the parameters and call the API.

**For stream_url, type `wss://[ngrok-subdomain].ngrok.app/media-stream`**
