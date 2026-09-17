import os
import json
import threading
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

TOKEN = "8925112663:AAECTaUL7PXfG1WtbegB4-GgX4BBbK3glI0"
ADMIN_ID = 8294462170  # <--- O'ZINGIZNING TELEGRAM ID RAQAMINGIZ
SECRET_ADMIN_COMMAND = "secretadmin"  # <--- ADMIN BUYRUG'I (Masalan: /secret_control)
ADMIN_PASSWORD = "20122607"  # <--- ADMIN PANEL PAROLI


USERS_FILE = "users.json"
LANGS_FILE = "user_langs.json"
BLOCKED_FILE = "blocked_users.json"
CACHE_FILE = "audio_cache.json"

AUTH_STATE, BROADCAST_STATE, BAN_STATE, UNBAN_STATE = range(4)

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot 24/7 ishlamoqda!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

def load_data(file_path, default):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users_list = set(load_data(USERS_FILE, []))
user_langs = load_data(LANGS_FILE, {})
blocked_users = set(load_data(BLOCKED_FILE, []))
audio_cache = load_data(CACHE_FILE, {})

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

TEXTS = {
    'uz': {
        'start': "Assalomu alaykum! Qo'shiq nomini yoki ijrochini yozing:",
        'search': "🔍 `{}` bo'yicha qidirilmoqda...",
        'sending': "⚡️ MP3 yuklanmoqda...",
        'not_found': "❌ Qo'shiq topilmadi.",
        'btn_lang': "🌐 Tilni o'zgartirish",
        'lang_changed': "✅ Til o'zgartirildi!",
        'blocked_msg': "🚫 Siz bloklangansiz!"
    },
    'ru': {
        'start': "Здравствуйте! Введите название песни или исполнителя:",
        'search': "🔍 Поиск по запросу `{}`...",
        'sending': "⚡️ Загрузка MP3...",
        'not_found': "❌ Песня не найдена.",
        'btn_lang': "🌐 Сменить язык",
        'lang_changed': "✅ Язык изменен!",
        'blocked_msg': "Вы заблокированы!"
    },
    'en': {
        'start': "Hello! Send the music title or artist name:",
        'search': "🔍 Searching for `{}`...",
        'sending': "⚡️ Downloading MP3...",
        'not_found': "❌ Track not found.",
        'btn_lang': "🌐 Change Language",
        'lang_changed': "✅ Language changed!",
        'blocked_msg': "🚫 You are blocked!"
    }
}

def get_user_lang(user_id):
    return user_langs.get(str(user_id), 'uz')

def get_main_keyboard(user_id):
    lang = get_user_lang(user_id)
    keyboard = [[KeyboardButton(TEXTS[lang]['btn_lang'])]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def is_blocked(user_id):
    return user_id in blocked_users

def format_duration(ms):
    if not ms: return "0:00"
    seconds = int(ms / 1000)
    m = math.floor(seconds / 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id):
        await update.message.reply_text(TEXTS['uz']['blocked_msg'])
        return

    if user_id not in users_list:
        users_list.add(user_id)
        save_data(USERS_FILE, list(users_list))

    if str(user_id) not in user_langs:
        keyboard = [
            [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="set_lang_uz")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
        ]
        await update.message.reply_text("Tilni tanlang / Select language:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        lang = get_user_lang(user_id)
        await update.message.reply_text(TEXTS[lang]['start'], reply_markup=get_main_keyboard(user_id))

async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = query.data.split("_")[-1]
    
    user_langs[str(user_id)] = lang
    save_data(LANGS_FILE, user_langs)
    
    await query.message.delete()
    await context.bot.send_message(
        chat_id=user_id,
        text=TEXTS[lang]['lang_changed'],
        reply_markup=get_main_keyboard(user_id)
    )

async def change_lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="set_lang_uz")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
    ]
    await update.message.reply_text("Tilni tanlang / Select language:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id): return

    text = update.message.text
    if text in [TEXTS['uz']['btn_lang'], TEXTS['ru']['btn_lang'], TEXTS['en']['btn_lang']]:
        await change_lang_command(update, context)
    else:
        await search_tracks(update, context, text)

# ----------------- TO'G'RIDAN-TO'G'RI OCHIQ API SEARCH -----------------

async def search_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    status_msg = await update.message.reply_text(TEXTS[lang]['search'].format(query_text), parse_mode="Markdown")

    tracks = []
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Saavn Open API orqali to'liq MP3 oqimini qidirish
        try:
            saavn_url = f"https://saavn.dev/api/search/songs?query={query_text}&limit=10"
            async with session.get(saavn_url, timeout=8) as resp:
                if resp.status == 200:
                    res_data = await resp.json()
                    results = res_data.get('data', {}).get('results', [])
                    for item in results:
                        download_urls = item.get('downloadUrl', [])
                        mp3_url = download_urls[-1]['url'] if download_urls else None
                        if mp3_url:
                            tracks.append({
                                'id': str(item.get('id')),
                                'title': f"{item.get('name')} - {item.get('primaryArtists')}",
                                'duration': format_duration(int(item.get('duration', 0)) * 1000),
                                'url': mp3_url
                            })
        except Exception as e:
            print(f"Saavn Error: {e}")

        # Zaxira: iTunes API
        if not tracks:
            try:
                itunes_url = f"https://itunes.apple.com/search?term={query_text}&entity=song&limit=10"
                async with session.get(itunes_url, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get('results', []):
                            tracks.append({
                                'id': str(item.get('trackId')),
                                'title': f"{item.get('artistName')} - {item.get('trackName')}",
                                'duration': format_duration(item.get('trackTimeMillis', 0)),
                                'url': item.get('previewUrl')
                            })
            except Exception as e:
                print(f"iTunes Error: {e}")

    if not tracks:
        await status_msg.edit_text(TEXTS[lang]['not_found'])
        return

    results_text = f"🔍 **{query_text}**\n\n"
    keyboard = []
    row = []

    context.user_data['search_results'] = {}

    for idx, item in enumerate(tracks, start=1):
        results_text += f"{idx}. **{item['title']}** `{item['duration']}`\n"
        context.user_data['search_results'][str(idx)] = item

        row.append(InlineKeyboardButton(str(idx), callback_data=f"music_{idx}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_search")])

    await status_msg.edit_text(
        results_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def track_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_search":
        await query.message.delete()
        return

    idx = query.data.replace("music_", "")
    item = context.user_data.get('search_results', {}).get(idx)

    if not item:
        await query.message.reply_text("❌ Qo'shiq topilmadi, qayta qidiring.")
        return

    await download_and_send(query.message, item, query.from_user.id)

async def download_and_send(message_obj, item, user_id):
    lang = get_user_lang(user_id)
    track_id = item['id']
    title = item['title']
    download_url = item['url']

    if track_id in audio_cache:
        try:
            await message_obj.reply_audio(
                audio=audio_cache[track_id]['file_id'],
                caption=f"🎧 **{audio_cache[track_id]['title']}**",
                parse_mode="Markdown"
            )
            return
        except Exception:
            del audio_cache[track_id]

    status_msg = await message_obj.reply_text(TEXTS[lang]['sending'])

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(download_url, timeout=20) as resp:
                if resp.status == 200:
                    audio_data = await resp.read()
                    sent_msg = await message_obj.reply_audio(
                        audio=audio_data,
                        filename=f"{title}.mp3",
                        title=title,
                        caption=f"🎧 **{title}**",
                        parse_mode="Markdown"
                    )

                    audio_cache[track_id] = {
                        'file_id': sent_msg.audio.file_id,
                        'title': title
                    }
                    save_data(CACHE_FILE, audio_cache)
                    await status_msg.delete()
                else:
                    await status_msg.edit_text(TEXTS[lang]['not_found'])
    except Exception as e:
        print(f"Download Error: {e}")
        await status_msg.edit_text(TEXTS[lang]['not_found'])

# ----------------- ADMIN PANEL -----------------

async def ask_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try: await update.message.delete()
    except Exception: pass

    msg = await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="🔑 **Admin panelga kirish uchun parolni kiriting:**"
    )
    context.user_data['prompt_msg_id'] = msg.message_id
    return AUTH_STATE

async def verify_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END

    try: await update.message.delete()
    except Exception: pass

    if 'prompt_msg_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_user.id,
                message_id=context.user_data['prompt_msg_id']
            )
        except Exception: pass

    if update.message.text.strip() == ADMIN_PASSWORD:
        keyboard = [
            [InlineKeyboardButton("📊 Statistikani ko'rish", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Foydalanuvchilar ID ro'yxati", callback_data="admin_users")],
            [InlineKeyboardButton("🚫 Bloklash", callback_data="admin_ban")],
            [InlineKeyboardButton("✅ Blokdan chiqarish", callback_data="admin_unban")],
            [InlineKeyboardButton("📢 Ommaviy xabar", callback_data="admin_broadcast")]
        ]
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="🔓 **Admin Panel:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="❌ **Parol noto'g'ri!**"
        )
        return ConversationHandler.END

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()

    if query.data == "admin_stats":
        msg = f"📊 **Bot statistikasi:**\n\nFoydalanuvchilar: **{len(users_list)}**\nKeshda: **{len(audio_cache)}**\nBloklanganlar: **{len(blocked_users)}**"
        await query.message.reply_text(msg, parse_mode="Markdown")
    
    elif query.data == "admin_users":
        users_str = "\n".join([f"`{u}`" for u in list(users_list)[:50]])
        await query.message.reply_text(f"👥 **IDlar:**\n\n{users_str}", parse_mode="Markdown")

    elif query.data == "admin_broadcast":
        await query.message.reply_text("📢 **Xabaringizni yuboring:** (/cancel — bekor qilish)")
        return BROADCAST_STATE

    elif query.data == "admin_ban":
        await query.message.reply_text("🚫 **ID yuboring:**")
        return BAN_STATE

    elif query.data == "admin_unban":
        await query.message.reply_text("✅ **ID yuboring:**")
        return UNBAN_STATE

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    count = 0
    for uid in users_list:
        if uid not in blocked_users:
            try:
                await update.message.copy(chat_id=uid)
                count += 1
            except Exception: pass
    await update.message.reply_text(f"✅ **{count}** ta foydalanuvchiga yuborildi!", parse_mode="Markdown")
    return ConversationHandler.END

async def process_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        blocked_users.add(target_id)
        save_data(BLOCKED_FILE, list(blocked_users))
        await update.message.reply_text(f"🚫 `{target_id}` bloklandi!", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri ID.")
    return ConversationHandler.END

async def process_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        if target_id in blocked_users:
            blocked_users.remove(target_id)
            save_data(BLOCKED_FILE, list(blocked_users))
            await update.message.reply_text(f"✅ `{target_id}` blokdan chiqarildi!", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Ro'yxatda yo'q.")
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri ID.")
    return ConversationHandler.END

async def cancel_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    admin_dialog = ConversationHandler(
        entry_points=[
            CommandHandler(SECRET_ADMIN_COMMAND, ask_admin_password),
            CallbackQueryHandler(admin_callback, pattern="^admin_broadcast$"),
            CallbackQueryHandler(admin_callback, pattern="^admin_ban$"),
            CallbackQueryHandler(admin_callback, pattern="^admin_unban$")
        ],
        states={
            AUTH_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_admin_password)],
            BROADCAST_STATE: [MessageHandler(filters.ALL & ~filters.COMMAND, start_broadcast)],
            BAN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_ban)],
            UNBAN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_unban)]
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_action)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(admin_dialog)
    
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^set_lang_"))
    app.add_handler(CallbackQueryHandler(track_select_callback, pattern="^(music_|cancel_search)"))
    app.add_handler(CallbackQueryHandler(admin_callback))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()