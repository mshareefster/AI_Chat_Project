# Huda AI

A private multi-model AI chat interface for an OpenAI-compatible AI gateway.

## Features

- Landing page with all selected models
- Chat page similar to a modern AI assistant
- Model switching
- File attachments
- Direct screenshot/image paste from clipboard
- PDF and DOCX text extraction
- Text/code file attachments
- API key remains on the backend
- React/Vite frontend
- FastAPI backend
- Apache reverse proxy
- Ready for `chat.hudamusthafa.tech`

## Important

This project assumes your common provider URL exposes an OpenAI-compatible endpoint:

`POST <AI_API_BASE_URL>/chat/completions`

If your provider uses a different endpoint or request format, only `backend/main.py` needs to be adjusted.

## Local setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal.

## EC2 deployment

Copy the project to `/var/www/huda-ai`.

Backend:

```bash
cd /var/www/huda-ai/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set:

```env
AI_API_BASE_URL=https://YOUR-API-BASE-URL/v1
AI_API_KEY=YOUR_REAL_KEY
PORT=8000
MAX_FILE_SIZE_MB=10
```

Build frontend:

```bash
cd /var/www/huda-ai/frontend
npm install
npm run build
```

Install/start systemd service:

```bash
cp /var/www/huda-ai/deploy/huda-ai.service /etc/systemd/system/huda-ai.service
systemctl daemon-reload
systemctl enable huda-ai
systemctl start huda-ai
systemctl status huda-ai
```

Apache modules on Amazon Linux may be needed:

```bash
sudo dnf install -y httpd mod_proxy mod_proxy_http mod_ssl
```

Enable/restart Apache:

```bash
sudo systemctl enable httpd
sudo systemctl restart httpd
```

Create the virtual host from `deploy/apache-chat.conf`.

Test backend:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected:

```json
{"status":"ok"}
```

## DNS

Create an A record:

`chat.hudamusthafa.tech` -> your EC2 public/Elastic IP

Then add HTTPS with Certbot after HTTP is working.

## Security

Never put `AI_API_KEY` in React/Vite `.env` or any frontend JavaScript. The browser should call `/api/chat`; only the FastAPI backend talks to the upstream provider.

For production, change CORS from `*` to:

`https://chat.hudamusthafa.tech`
