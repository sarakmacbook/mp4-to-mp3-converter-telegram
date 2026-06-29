# 🎵 MP4 to MP3 Telegram Bot

A Telegram bot that converts MP4 videos to MP3 audio. Supports:
- **Uploaded MP4 files** (max 50MB)
- **YouTube links** (extracts audio track)

## 🚀 Deploy to Railway

### 1. Create Telegram Bot
- Message [@BotFather](https://t.me/botfather) on Telegram
- Run `/newbot` and follow instructions
- Copy your **Bot Token**

### 2. Fork/Create GitHub Repo
Push all these files to a new GitHub repository.

### 3. Deploy on Railway
1. Go to [Railway](https://railway.app) → New Project → Deploy from GitHub repo
2. Select your repository
3. Go to **Variables** tab → Add `BOT_TOKEN`
4. Deploy!

### 4. Set Webhook (Optional but Recommended)
1. After first deploy, go to **Settings &gt; Domains** in Railway
2. Copy your domain (e.g., `https://your-app.railway.app`)
3. Add environment variable: `WEBHOOK_URL=https://your-app.railway.app`
4. Redeploy

## 🛠️ Local Development

```bash
# 1. Install ffmpeg (macOS)
brew install ffmpeg

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Edit .env with your BOT_TOKEN

# 5. Run
python bot.py
