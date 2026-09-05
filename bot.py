import os
import json
import yt_dlp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8925112663:AAECTaUL7PXfG1WtbegB4-GgX4BBbK3glI0"
USERS_FILE = "users.json"

os.makedirs("downloads", exist_ok=True)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

known_users = load_users()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in known_users:
        known_users.add(user_id)
        save_users(known_users)
        
        keyboard = [[KeyboardButton("/start")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "Assalomu alaykum! Musiqa nomini yuboring:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Xush kelibsiz! Qaysi musiqani qidiryapsiz? Nomini yuboring:")

async def search_and_send_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    status_msg = await update.message.reply_text(f"🔍 `{query}` bo'yicha musiqa qidirilmoqda...", parse_mode="Markdown")

    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'scsearch1',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            file_path = ydl.prepare_filename(info)
            file_path = os.path.splitext(file_path)[0] + ".mp3"
            title = info.get('title', 'Musiqa')

        if file_path and os.path.exists(file_path):
            await status_msg.edit_text("⚡️ Musiqa yuborilmoqda...")
            with open(file_path, 'rb') as audio:
                await update.message.reply_audio(
                    audio=audio,
                    title=title,
                    caption=f"🎧 **{title}**\n\n🤖 @musiqa_qidiruv_bot orqali yuklandi",
                    parse_mode="Markdown"
                )
            await status_msg.delete()
            os.remove(file_path)
        else:
            await status_msg.edit_text("❌ Musiqa fayli topilmadi.")

    except Exception as e:
        print(f"Server Log Xatosi: {e}")
        await status_msg.edit_text("❌ Musiqa topilmadi yoki yuklashda xatolik yuz berdi.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_and_send_audio))
    
    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()