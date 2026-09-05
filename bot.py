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
ADMIN_ID = 20122607  # <--- O'ZINGIZNING TELEGRAM ID RAQAMINGIZNI YOZING

USERS_FILE = "users.json"
LANGS_FILE = "user_langs.json"
BROADCAST_STATE = 1

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
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users_list = set(load_data(USERS_FILE, []))
user_langs = load_data(LANGS_FILE, {})

TEXTS = {
    'uz': {
        'start': "Assalomu alaykum! Musiqa nomini yuboring yoki menyudan foydalaning:",
        'search': "🔍 `{}` bo'yicha musiqa qidirilmoqda...",
        'sending': "⚡️ Musiqa yuborilmoqda...",
        'not_found': "❌ Musiqa topilmadi yoki yuklashda xatolik yuz berdi.",
        'top_title': "🔥 **Eng ommabop top-10 musiqalar:**\n\nBiror birini tanlab bosing:",
        'lang_select': "Tilni tanlang / Select language / Выберите язык:",
        'lang_changed': "🇺🇿 Til o'zgartirildi!",
        'btn_top': "🔥 Top-10 Musiqa",
        'btn_lang': "🌐 Tilni o'zgartirish",
        'admin_stats': "📊 **Bot statistikasi:**\n\nJami foydalanuvchilar: **{}** ta",
        'admin_broadcast_ask': "Ommaviy xabarni yuboring (Matn, rasm yoki video):",
        'broadcast_success': "✅ Xabar barcha foydalanuvchilarga yuborildi!",
        'similar_title': "\n\n👇 **O'xshash variantlar:**"
    },
    'ru': {
        'start': "Здравствуйте! Отправьте название музыки или используйте меню:",
        'search': "🔍 Идет поиск музыки по запросу `{}`...",
        'sending': "⚡️ Музыка отправляется...",
        'not_found': "❌ Музыка не найдена или произошла ошибка при загрузке.",
        'top_title': "🔥 **Топ-10 популярных треков:**\n\nВыберите один из них:",
        'lang_select': "Выберите язык / Select language:",
        'lang_changed': "🇷🇺 Язык изменен!",
        'btn_top': "🔥 Топ-10 Треков",
        'btn_lang': "🌐 Сменить язык",
        'admin_stats': "📊 **Статистика бота:**\n\nВсего пользователей: **{}**",
        'admin_broadcast_ask': "Отправьте рассылку (Текст, фото или видео):",
        'broadcast_success': "✅ Рассылка успешно отправлена всем!",
        'similar_title': "\n\n👇 **Похожие варианты:**"
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
        'admin_stats': "📊 **Bot Statistics:**\n\nTotal Users: **{}**",
        'admin_broadcast_ask': "Send the broadcast message (Text, photo or video):",
        'broadcast_success': "✅ Broadcast successfully sent!",
        'similar_title': "\n\n👇 **Similar tracks:**"
    }
}

TOP_TRACKS = [
    "Alan Walker - Darkside",
    "Indila - Derniere Danse",
    "The Weeknd - Blinding Lights",
    "Eminem - Mockingbird",
    "Glass Animals - Heat Waves",
    "Tom Odell - Another Love",
    "Xcho - Ты и Я",
    "Miyagi & Эндшпиль - I Got Love",
    "Jony - Комета",
    "Soolking - Zemër"
]

def get_user_lang(user_id):
    return user_langs.get(str(user_id), 'uz')

def get_main_keyboard(user_id):
    lang = get_user_lang(user_id)
    keyboard = [
        [KeyboardButton(TEXTS[lang]['btn_top']), KeyboardButton(TEXTS[lang]['btn_lang'])]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
    lang = get_user_lang(user_id)
    
    keyboard = []
    for idx, track in enumerate(TOP_TRACKS):
        # Callback data uzunligini chegaralash uchun prefiks ishlatamiz
        keyboard.append([InlineKeyboardButton(f"🎵 {track}", callback_data=f"dl_{idx}")])
    
    await update.message.reply_text(
        TEXTS[lang]['top_title'],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def top_track_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.replace("dl_", ""))
    track_name = TOP_TRACKS[idx]
    await download_and_send(query.message, track_name, query.from_user.id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text in [TEXTS['uz']['btn_top'], TEXTS['ru']['btn_top'], TEXTS['en']['btn_top']]:
        await show_top_tracks(update, context)
    elif text in [TEXTS['uz']['btn_lang'], TEXTS['ru']['btn_lang'], TEXTS['en']['btn_lang']]:
        await change_lang_command(update, context)
    else:
        await download_and_send(update.message, text, user_id)

# Tezlashtirilgan va xatosiz yuklash funksiyasi
async def download_and_send(message_obj, query, user_id):
    lang = get_user_lang(user_id)
    status_msg = await message_obj.reply_text(TEXTS[lang]['search'].format(query), parse_mode="Markdown")

    # Qidirish va yuklash bitta bosqichda bajariladi
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'scsearch3',
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
            # Birdaniga yuklaymiz (Double-query tezlikni sekinlashtirayotgan edi)
            info = ydl.extract_info(query, download=True)
            
            if not info:
                await status_msg.edit_text(TEXTS[lang]['not_found'])
                return

            if 'entries' in info and info['entries']:
                entries = info['entries']
                primary_entry = entries[0]
            else:
                entries = [info]
                primary_entry = info

            file_path = ydl.prepare_filename(primary_entry)
            file_path = os.path.splitext(file_path)[0] + ".mp3"
            title = primary_entry.get('title', 'Musiqa')

        if file_path and os.path.exists(file_path):
            await status_msg.edit_text(TEXTS[lang]['sending'])
            
            similar_buttons = []
            if len(entries) > 1:
                for alt_track in entries[1:3]:
                    alt_title = alt_track.get('title', 'Trek')
                    display_title = alt_title[:30] + "..." if len(alt_title) > 30 else alt_title
                    # Callback buyrug'ini qisqa qilamiz
                    similar_buttons.append([InlineKeyboardButton(f"🎵 {display_title}", callback_data=f"search_{display_title}")])

            reply_markup = InlineKeyboardMarkup(similar_buttons) if similar_buttons else None
            caption_text = f"🎧 **{title}**\n\n🤖 @musiqa_qidiruv_bot"
            
            if similar_buttons:
                caption_text += TEXTS[lang]['similar_title']

            with open(file_path, 'rb') as audio:
                await message_obj.reply_audio(
                    audio=audio,
                    title=title,
                    caption=caption_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            await status_msg.delete()
            os.remove(file_path)
        else:
            await status_msg.edit_text(TEXTS[lang]['not_found'])

    except Exception as e:
        print(f"Log error: {e}")
        await status_msg.edit_text(TEXTS[lang]['not_found'])

async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    search_query = query.data.replace("search_", "")
    await download_and_send(query.message, search_query, query.from_user.id)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    keyboard = [
        [InlineKeyboardButton("📊 Statistikani ko'rish", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Ommaviy xabar yuborish", callback_data="admin_broadcast")]
    ]
    await update.message.reply_text("⚙️ **Admin Panel:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    await query.answer()

    if query.data == "admin_stats":
        lang = get_user_lang(ADMIN_ID)
        await query.message.reply_text(TEXTS[lang]['admin_stats'].format(len(users_list)), parse_mode="Markdown")
    elif query.data == "admin_broadcast":
        await query.message.reply_text("📢 **Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring:**")
        return BROADCAST_STATE

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    count = 0
    for uid in users_list:
        try:
            await update.message.copy(chat_id=uid)
            count += 1
        except Exception:
            pass
            
    await update.message.reply_text(f"✅ Xabar **{count}** ta foydalanuvchiga muvaffaqiyatli yetkazildi!", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Reklama yuborish bekor qilindi.")
    return ConversationHandler.END

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_broadcast$")],
        states={
            BROADCAST_STATE: [MessageHandler(filters.ALL & ~filters.COMMAND, start_broadcast)]
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(broadcast_handler)
    
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^set_lang_"))
    app.add_handler(CallbackQueryHandler(top_track_download_callback, pattern="^dl_"))
    app.add_handler(CallbackQueryHandler(search_callback, pattern="^search_"))
    app.add_handler(CallbackQueryHandler(admin_callback))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()