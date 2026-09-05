import os
import sqlite3
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import yt_dlp

# Loglarni sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = "8856479465:AAE2rHYmD0B92hvsC7O_dl83SARd94w1QDo"  # <-- Tokeningizni joylang
DB_NAME = "music_bot.db"

# ==================== BAZA BILAN ISHLASH ====================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS music_cache (
            video_id TEXT PRIMARY KEY,
            file_id TEXT,
            title TEXT,
            performer TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(user_id: int, first_name: str, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
        (user_id, first_name, username)
    )
    conn.commit()
    conn.close()

def get_cached_music(video_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, title, performer FROM music_cache WHERE video_id = ?", (video_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def save_music_cache(video_id: str, file_id: str, title: str, performer: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO music_cache (video_id, file_id, title, performer) VALUES (?, ?, ?, ?)",
        (video_id, file_id, title, performer)
    )
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM music_cache")
    cache_count = cursor.fetchone()[0]
    conn.close()
    return users_count, cache_count

# ==================== BOT HANDLERLARI ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.first_name, user.username)
    
    await update.message.reply_text(
        f"Salom, {user.first_name}! 🎵\n\n"
        f"Menga qoʻshiq yoki ijrochi nomini yuboring, men uni topib beraman!"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_count, cache_count = get_stats()
    await update.message.reply_text(
        f"📊 **Bot Statistikasi:**\n\n"
        f"👤 Foydalanuvchilar: **{users_count}**\n"
        f"🎵 Saqlangan musiqalar (Kesh): **{cache_count}**",
        parse_mode="Markdown"
    )

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    status_msg = await update.message.reply_text("🔍 Natijalar qidirilmoqda...")

    ydl_opts = {
        'default_search': 'ytsearch5',
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
    }

    loop = asyncio.get_running_loop()

    def get_info():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=False)

    try:
        info = await loop.run_in_executor(None, get_info)
        
        if not info or 'entries' not in info:
            await status_msg.edit_text("❌ Hech qanday qoʻshiq topilmadi.")
            return

        entries = [e for e in info['entries'] if e]

        if not entries:
            await status_msg.edit_text("❌ Hech qanday qoʻshiq topilmadi.")
            return

        keyboard = []
        for idx, entry in enumerate(entries):
            title = entry.get('title', 'Nomaʼlum')[:35]
            video_id = entry.get('id')
            if video_id:
                keyboard.append([InlineKeyboardButton(f"{idx + 1}. {title}", callback_data=f"dl_{video_id}")])

        if not keyboard:
            await status_msg.edit_text("❌ Natijalarni qayta ishlashda xatolik boʻldi.")
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        await status_msg.edit_text("👇 Kerakli qoʻshiqni tanlang:", reply_markup=reply_markup)

    except Exception as e:
        logging.error(f"Qidiruvda xatolik: {e}")
        await status_msg.edit_text("❌ Qoʻshiqni qidirishda xatolik yuz berdi.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("dl_"):
        return

    video_id = data.replace("dl_", "")

    # 1. Keshdan tekshirish
    cached_data = get_cached_music(video_id)
    if cached_data:
        file_id, title, performer = cached_data
        await query.message.reply_audio(
            audio=file_id,
            title=title,
            performer=performer,
            caption=f"🎧 **{title}**\n⚡️ *NodirLab Bot*",
            parse_mode="Markdown"
        )
        return

    # 2. FFMPEG REJIMISIZ YUKLAB OLISH (FFmpeg talab qilmaydi)
    url = f"https://www.youtube.com/watch?v={video_id}"
    status_msg = await query.message.reply_text("📥 Qoʻshiq yuklanmoqda...")

    ydl_opts = {
        'format': 'm4a/bestaudio/best',  # FFmpeg convert qilmasdan tayyor m4a formatida oladi
        'outtmpl': f'downloads/{video_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
    }

    loop = asyncio.get_running_loop()

    def download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            video_info = ydl.extract_info(url, download=True)
            ext = video_info.get('ext', 'm4a')
            file_path = f"downloads/{video_id}.{ext}"
            title = video_info.get('title', 'Qoʻshiq')
            performer = video_info.get('uploader', 'Nomaʼlum')
            return file_path, title, performer

    try:
        file_path, title, performer = await loop.run_in_executor(None, download)
        await status_msg.edit_text("⚡️ Yuborilmoqda...")

        with open(file_path, 'rb') as audio_file:
            sent_message = await query.message.reply_audio(
                audio=audio_file,
                title=title,
                performer=performer,
                caption=f"🎧 **{title}**",
                parse_mode="Markdown"
            )

        if sent_message.audio:
            save_music_cache(video_id, sent_message.audio.file_id, title, performer)

        await status_msg.delete()

        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logging.error(f"Yuklashda xatolik: {e}")
        await status_msg.edit_text("❌ Audio faylni yuklab olishda xatolik boʻldi.")

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("NodirLab_bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()