"""
Telegram Bot: MP4 to MP3 Converter
Supports: Uploaded MP4 files & YouTube links
Deploy: Railway (with nixpacks.toml or Dockerfile)
"""

import os
import logging
import tempfile
import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ─── Configuration ───────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # e.g. https://your-app.railway.app

# Telegram file size limit (20MB for bots, 50MB with local API)
MAX_FILE_SIZE_MB = 50

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Helper Functions ──────────────────────────────────────────────────────────

def get_ydl_opts(output_path: str, extract_audio: bool = True) -> dict:
    """yt-dlp options for extracting audio."""
    opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }
    if extract_audio:
        opts.update({
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    return opts


async def convert_mp4_to_mp3(input_path: str, output_path: str) -> bool:
    """Convert local MP4 file to MP3 using ffmpeg."""
    import subprocess
    try:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vn",                    # no video
            "-acodec", "libmp3lame",
            "-ab", "192k",
            "-ar", "44100",
            "-y",                     # overwrite output
            output_path,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
        )
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.error(f"FFmpeg conversion error: {e}")
        return False


async def download_youtube_audio(url: str, output_dir: str) -> str | None:
    """Download audio from YouTube URL as MP3."""
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    opts = get_ydl_opts(output_template, extract_audio=True)
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Find the actual output file
            title = info.get("title", "audio")
            expected = os.path.join(output_dir, f"{title}.mp3")
            if os.path.exists(expected):
                return expected
            
            # Fallback: search for any mp3 in output_dir
            mp3_files = list(Path(output_dir).glob("*.mp3"))
            return str(mp3_files[0]) if mp3_files else None
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return None


def cleanup_files(*paths: str):
    """Delete temporary files."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
                logger.info(f"Cleaned up: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")


# ─── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message."""
    welcome_text = (
        "🎵 *MP4 → MP3 Converter Bot*\n\n"
        "Send me:\n"
        "• An *MP4 video file* — I'll extract the audio as MP3\n"
        "• A *YouTube link* — I'll download the audio track\n\n"
        "⚠️ Max file size: 50MB\n"
        "⏱️ Large files may take a moment to process."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help."""
    help_text = (
        "📖 *How to use:*\n\n"
        "1️⃣ Upload an MP4 file directly\n"
        "2️⃣ Paste a YouTube URL\n\n"
        "The bot will convert and send back the MP3 audio file.\n\n"
        "⚠️ *Limits:*\n"
        "• Max upload: 50MB\n"
        "• Supported: MP4, YouTube links\n"
        "• Processing time depends on file size"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded video files."""
    message = update.message
    chat_id = message.chat_id
    
    # Check file size
    video = message.video or message.document
    if not video:
        await message.reply_text("❌ Please send a valid video file.")
        return
    
    file_size_mb = (video.file_size or 0) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        await message.reply_text(
            f"❌ File too large ({file_size_mb:.1f}MB). "
            f"Max allowed: {MAX_FILE_SIZE_MB}MB"
        )
        return
    
    status_msg = await message.reply_text("⏳ Downloading your video...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Download the video
        try:
            video_file = await video.get_file()
            input_path = os.path.join(tmpdir, "input.mp4")
            await video_file.download_to_drive(input_path)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            await status_msg.edit_text("❌ Failed to download video.")
            return
        
        await status_msg.edit_text("🔄 Converting to MP3...")
        
        # Convert to MP3
        output_path = os.path.join(tmpdir, "output.mp3")
        success = await convert_mp4_to_mp3(input_path, output_path)
        
        if not success:
            await status_msg.edit_text("❌ Conversion failed. Please try again.")
            return
        
        # Send the MP3
        await status_msg.edit_text("📤 Sending audio file...")
        try:
            with open(output_path, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title="Converted Audio",
                    performer="MP3 Bot",
                    caption="✅ Here's your MP3!",
                )
            await status_msg.delete()
        except Exception as e:
            logger.error(f"Send failed: {e}")
            await status_msg.edit_text("❌ Failed to send audio file.")
        
        cleanup_files(input_path, output_path)


async def handle_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube URLs."""
    message = update.message
    url = message.text.strip()
    chat_id = message.chat_id
    
    # Basic URL validation
    if not any(domain in url for domain in ["youtube.com", "youtu.be", "youtube"]):
        await message.reply_text(
            "❌ Please send a valid YouTube URL.\n"
            "Supported: youtube.com, youtu.be"
        )
        return
    
    status_msg = await message.reply_text("🎵 Downloading audio from YouTube...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = await download_youtube_audio(url, tmpdir)
        
        if not output_path:
            await status_msg.edit_text(
                "❌ Failed to download. The video may be restricted or unavailable."
            )
            return
        
        # Check file size
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(
                f"❌ File too large ({file_size_mb:.1f}MB). "
                f"Max: {MAX_FILE_SIZE_MB}MB"
            )
            cleanup_files(output_path)
            return
        
        await status_msg.edit_text("📤 Sending audio file...")
        try:
            with open(output_path, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title="YouTube Audio",
                    performer="MP3 Bot",
                    caption="✅ YouTube audio converted to MP3!",
                )
            await status_msg.delete()
        except Exception as e:
            logger.error(f"Send failed: {e}")
            await status_msg.edit_text("❌ Failed to send audio file.")
        
        cleanup_files(output_path)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle non-URL text messages."""
    await update.message.reply_text(
        "🤔 I only understand:\n"
        "• MP4 video files\n"
        "• YouTube links\n\n"
        "Send /help for more info."
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "⚠️ An error occurred. Please try again later."
        )


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is required!")
    
    # Build application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"youtube\.com|youtu\.be"), handle_youtube))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)
    
    # Run
    if WEBHOOK_URL:
        # Webhook mode (recommended for Railway)
        logger.info(f"Starting webhook on port {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        # Polling mode (local dev)
        logger.info("Starting polling mode...")
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
