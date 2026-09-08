import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import yt_dlp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

TOKEN = "8925112663:AAECTaUL7PXfG1WtbegB4-GgX4BBbK3glI0"
ADMIN_ID = 8294462170  # <--- TELEGRAM ID RAQAMINGIZ
SECRET_ADMIN_COMMAND = "secretAdmin"  # <--- MAXFIY BUYRUQ
ADMIN_PASSWORD = "20122607"  # <--- ADMIN PAROLI

USERS_FILE = "users.json"
LANGS_FILE = "user_langs.json"
BLOCKED_FILE = "blocked_users.json"
CACHE_FILE = "audio_cache.json"

AUTH_STATE, BROADCAST_STATE, BAN_STATE, UNBAN_STATE = range(4)

os.makedirs("downloads", exist_ok=True)

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlamoqda!")

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

TEXTS = {
    'uz': {
        'start': "Assalomu alaykum! Musiqa nomini yuboring yoki menyudan foydalaning:",
        'search': "🔍 `{}` bo'yicha musiqa qidirilmoqda...",
        'sending': "⚡️ Musiqa yuborilmoqda...",
        'not_found': "❌ Musiqa topilmadi yoki yuklashda xatolik yuz berdi.",
        'top_title': "🔥 **Eng ommabop top-10 musiqalar:**\n\nBiror birini tanlab bosing:",
        'lang_select': "Tilni tanlang / Select language:",
        'lang_changed': "🇺🇿 Til o'zgartirildi!",
        'btn_top': "🔥 Top-10 Musiqa",
        'btn_lang': "🌐 Tilni o'zgartirish",
        'blocked_msg': "🚫 Siz botdan foydalanish uchun bloklangansiz!"
    },
    'ru': {
        'start': "Здравствуйте! Отправьте название музыки или используйте меню:",
        'search': "🔍 Идет поиск музыки по запросу `{}`...",
        'sending': "⚡️ Музыка отправляется...",
        'not_found': "❌ Музыка не найдена или произошла ошибка при загрузке.",
        'top_title': "🔥 **Топ-10 популярных треков:**\n\nВыберите один из них:",
        'lang_select': "Выберите язык:",
        'lang_changed': "🇷🇺 Язык изменен!",
        'btn_top': "🔥 Топ-10 Треков",
        'btn_lang': "🌐 Сменить язык",
        'blocked_msg': "🚫 Вы заблокированы в этом боте!"
    },
    'en': {
        'start': "Hello! Send the music title or use the menu below:",
        'search': "🔍 Searching for `{}`...",
        'sending': "⚡️ Sending audio...",
        'not_found': "❌ Music not found or download failed.",
        'top_title': "🔥 **Top-10 popular tracks:**\n\nSelect one to download:",
        'lang_select': "Select language:",
        'lang_changed': "🇬🇧 Language changed!",
        'btn_top': "🔥 Top-10 Tracks",
        'btn_lang': "🌐 Change Language",
        'blocked_msg': "🚫 You are blocked from using this bot!"
    }
}

TOP_TRACKS = [
    "Alan Walker - Darkside", "Indila - Derniere Danse", "The Weeknd - Blinding Lights",
    "Eminem - Mockingbird", "Glass Animals - Heat Waves", "Tom Odell - Another Love",
    "Xcho - Ты и Я", "Miyagi & Эндшпиль - I Got Love", "Jony - Комета", "Soolking - Zemër"
]

def get_user_lang(user_id):
    return user_langs.get(str(user_id), 'uz')

def get_main_keyboard(user_id):
    lang = get_user_lang(user_id)
    keyboard = [
        [KeyboardButton(TEXTS[lang]['btn_top']), KeyboardButton(TEXTS[lang]['btn_lang'])]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def is_blocked(user_id):
    return user_id in blocked_users

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

async def show_top_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id): return
    lang = get_user_lang(user_id)
    
    keyboard = []
    for idx, track in enumerate(TOP_TRACKS):
        keyboard.append([InlineKeyboardButton(f"🎵 {track}", callback_data=f"dl_{idx}")])
    
    await update.message.reply_text(
        TEXTS[lang]['top_title'],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def top_track_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if is_blocked(query.from_user.id): return
    idx = int(query.data.replace("dl_", ""))
    track_name = TOP_TRACKS[idx]
    await download_and_send(query.message, track_name, query.from_user.id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id):
        await update.message.reply_text(TEXTS['uz']['blocked_msg'])
        return

    text = update.message.text
    if text in [TEXTS['uz']['btn_top'], TEXTS['ru']['btn_top'], TEXTS['en']['btn_top']]:
        await show_top_tracks(update, context)
    elif text in [TEXTS['uz']['btn_lang'], TEXTS['ru']['btn_lang'], TEXTS['en']['btn_lang']]:
        await change_lang_command(update, context)
    else:
        await download_and_send(update.message, text, user_id)

async def download_and_send(message_obj, query, user_id):
    lang = get_user_lang(user_id)
    clean_query = query.strip().lower()

    if clean_query in audio_cache:
        cached_data = audio_cache[clean_query]
        caption_text = f"🎧 **{cached_data['title']}**\n⚡️ _(Tezkor keshdan yuborildi)_"
        try:
            await message_obj.reply_audio(
                audio=cached_data['file_id'],
                caption=caption_text,
                parse_mode="Markdown"
            )
            return
        except Exception:
            del audio_cache[clean_query]

    status_msg = await message_obj.reply_text(TEXTS[lang]['search'].format(query), parse_mode="Markdown")

    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'scsearch1',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_query, download=True)
            if not info:
                await status_msg.edit_text(TEXTS[lang]['not_found'])
                return

            entries = info.get('entries', [info])
            if not entries:
                await status_msg.edit_text(TEXTS[lang]['not_found'])
                return

            primary_entry = entries[0]
            filename = ydl.prepare_filename(primary_entry)
            title = primary_entry.get('title', 'Musiqa')

        if filename and os.path.exists(filename):
            await status_msg.edit_text(TEXTS[lang]['sending'])
            caption_text = f"🎧 **{title}**"

            with open(filename, 'rb') as audio:
                sent_message = await message_obj.reply_audio(
                    audio=audio, title=title, caption=caption_text, parse_mode="Markdown"
                )
                
                file_id = sent_message.audio.file_id
                audio_cache[clean_query] = {
                    'file_id': file_id,
                    'title': title
                }
                save_data(CACHE_FILE, audio_cache)

            await status_msg.delete()
            if os.path.exists(filename):
                os.remove(filename)
        else:
            await status_msg.edit_text(TEXTS[lang]['not_found'])

    except Exception as e:
        print(f"Log error: {e}")
        await status_msg.edit_text(TEXTS[lang]['not_found'])

async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if is_blocked(query.from_user.id): return
    search_query = query.data.replace("search_", "")
    await download_and_send(query.message, search_query, query.from_user.id)

# ----------------- PAROL O'CHIRILADIGAN ADMIN PANEL -----------------

async def ask_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    
    # Buyruq xabarini o'chirish (ixtiyoriy)
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

    # Foydalanuvchi yozgan PAROL XABARINI DARHOL O'CHIRISH
    try:
        await update.message.delete()
    except Exception:
        pass

    # Bot bergan savol xabarini o'chirish
    if 'prompt_msg_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_user.id,
                message_id=context.user_data['prompt_msg_id']
            )
        except Exception:
            pass

    if update.message.text.strip() == ADMIN_PASSWORD:
        keyboard = [
            [InlineKeyboardButton("📊 Statistikani ko'rish", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Foydalanuvchilar ID ro'yxati", callback_data="admin_users")],
            [InlineKeyboardButton("🚫 Foydalanuvchini bloklash", callback_data="admin_ban")],
            [InlineKeyboardButton("✅ Blokdan chiqarish", callback_data="admin_unban")],
            [InlineKeyboardButton("📢 Ommaviy xabar yuborish", callback_data="admin_broadcast")]
        ]
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="🔓 **Parol to'g'ri! Admin Panel:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="❌ **Parol noto'g'ri!** Kirish rad etildi."
        )
        return ConversationHandler.END

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()

    if query.data == "admin_stats":
        msg = f"📊 **Bot statistikasi:**\n\n"
        msg += f"Jami foydalanuvchilar: **{len(users_list)}** ta\n"
        msg += f"Keshdagi musiqalar: **{len(audio_cache)}** ta\n"
        msg += f"Bloklanganlar: **{len(blocked_users)}** ta"
        await query.message.reply_text(msg, parse_mode="Markdown")
    
    elif query.data == "admin_users":
        users_str = "\n".join([f"`{u}`" for u in list(users_list)[:50]])
        await query.message.reply_text(f"👥 **Foydalanuvchilar ID ro'yxati:**\n\n{users_str}", parse_mode="Markdown")

    elif query.data == "admin_broadcast":
        await query.message.reply_text("📢 **Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring:**\n\n_(Bekor qilish uchun /cancel yuboring)_")
        return BROADCAST_STATE

    elif query.data == "admin_ban":
        await query.message.reply_text("🚫 **Bloklamoqchi bo'lgan foydalanuvchining ID raqamini yuboring:**\n\n_(Bekor qilish uchun /cancel yuboring)_")
        return BAN_STATE

    elif query.data == "admin_unban":
        await query.message.reply_text("✅ **Blokdan chiqarmoqchi bo'lgan ID raqamni yuboring:**\n\n_(Bekor qilish uchun /cancel yuboring)_")
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
    await update.message.reply_text(f"✅ Xabar **{count}** ta foydalanuvchiga muvaffaqiyatli yetkazildi!", parse_mode="Markdown")
    return ConversationHandler.END

async def process_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        blocked_users.add(target_id)
        save_data(BLOCKED_FILE, list(blocked_users))
        await update.message.reply_text(f"🚫 `{target_id}` muvaffaqiyatli bloklandi!", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Xatolik! Faqat raqamli Telegram ID yuboring.")
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
            await update.message.reply_text("⚠️ Bu ID bloklanganlar ro'yxatida yo'q.")
    except ValueError:
        await update.message.reply_text("❌ Xatolik! Faqat raqamli Telegram ID yuboring.")
    return ConversationHandler.END

async def cancel_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Amal bekor qilindi.")
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
    app.add_handler(CallbackQueryHandler(top_track_download_callback, pattern="^dl_"))
    app.add_handler(CallbackQueryHandler(search_callback, pattern="^search_"))
    app.add_handler(CallbackQueryHandler(admin_callback))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()