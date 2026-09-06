from flask import Flask
from threading import Thread
import os
import logging
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedPhoto
from telegram.error import RetryAfter, TimedOut, BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    InlineQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from functools import wraps

app = Flask('')

@app.route('/')
def home():
    return "Bot ishlayapti!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN muhit o'zgaruvchisi topilmadi! "
        "Render'da Environment tab'iga o'tib, Key='BOT_TOKEN', Value=<bot tokeningiz> qo'shing."
    )
MANAGER_USERNAME = "azizbek_mebel"

# Maxfiy kanal ID raqami (agar kerak bo'lsa)
DUMP_CHANNEL_ID = -1004346956457

# --- ADMIN HIMOYASI ---
ADMIN_IDS = {760912345}

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            lang = get_current_lang()
            deny_text = "⛔ Sizda bu amalni bajarish huquqi yo'q." if lang != "ru" else "⛔ У вас нет прав для этого действия."
            if update.callback_query:
                await update.callback_query.answer(deny_text, show_alert=True)
            else:
                await update.message.reply_text(deny_text)
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper

DB_DIR = "/data"
if not os.path.exists(DB_DIR):
    try:
        os.makedirs(DB_DIR, exist_ok=True)
    except Exception:
        DB_DIR = "."

DB_PATH = os.path.join(DB_DIR, "furniture_bot.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

_LANG_CACHE = {"value": None}

(
    ADD_CAT, ADD_PHOTO, ADD_DESC, 
    ADD_BRAND_MENU, ADD_NEW_BRAND, ADD_COLOR_PHOTO, ADD_COLOR_NAME,
    SET_LOGO, SET_INFO, SET_WELCOME, DEL_BRAND, EDIT_COLOR_NAME,
    ADD_VIDEO_CAT, ADD_VIDEO_FILE, ADD_VIDEO_DESC, BROADCAST_TEXT,
    EDIT_COLOR_BRAND, EDIT_COLOR_SELECT
) = range(18)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            title TEXT,
            description TEXT,
            photo TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN doc_file_id TEXT")
    except Exception:
        pass
        
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT,
            color_name TEXT,
            photo TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE colors ADD COLUMN doc_file_id TEXT")
    except Exception:
        pass
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            file_id TEXT,
            file_type TEXT,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_id INTEGER
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_colors_brand ON colors(brand)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_cat ON videos(category)")
    
    default_brands = ["Stoleshnitsa", "Akril: Kashtan", "Akril: Kastaman", "MDF / LDSP", "Yeger Premium"]
    for b in default_brands:
        cursor.execute("INSERT OR IGNORE INTO brands (brand_name) VALUES (?)", (b,))
        
    cursor.execute("SELECT value FROM settings WHERE key = 'welcome_text'")
    if not cursor.fetchone():
        default_welcome = (
            "Assalomu alaykum, {user_name}!\n"
            "Zamonaviy mebellar katalogiga xush kelibsiz.\n"
            "Kerakli bo'limni tanlang:"
        )
        cursor.execute("INSERT INTO settings (key, value) VALUES ('welcome_text', ?)", (default_welcome,))

    cursor.execute("SELECT value FROM settings WHERE key = 'language'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES ('language', 'uz')")

    conn.commit()
    conn.close()

init_db()

def main_menu_keyboard(lang="uz"):
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("📁 Каталог", callback_data="main_catalog"),
             InlineKeyboardButton("🎨 Цвета / Бренды", callback_data="main_colors")],
            [InlineKeyboardButton("💡 Полезные видео и лайфхаки", callback_data="main_videos")],
            [InlineKeyboardButton("📞 Контакты", callback_data="main_info"),
             InlineKeyboardButton("🌐 Язык", callback_data="main_lang")],
            [InlineKeyboardButton("🔄 Обновить бот", callback_data="back_to_main")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📁 Katalog", callback_data="main_catalog"),
             InlineKeyboardButton("🎨 Ranglar / Brendlar", callback_data="main_colors")],
            [InlineKeyboardButton("💡 Foydali videolar va layfhaklar", callback_data="main_videos")],
            [InlineKeyboardButton("📞 Aloqa", callback_data="main_info"),
             InlineKeyboardButton("🌐 Til", callback_data="main_lang")],
            [InlineKeyboardButton("🔄 Botni yangilash", callback_data="back_to_main")]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_current_lang():
    if _LANG_CACHE["value"] is not None:
        return _LANG_CACHE["value"]
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'language'")
        res = cursor.fetchone()
        conn.close()
        lang = res[0] if res else "uz"
        _LANG_CACHE["value"] = lang
        return lang
    except:
        return "uz"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_current_lang()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, first_name, username) 
        VALUES (?, ?, ?)
    """, (user.id, user.first_name, user.username))
    cursor.execute("""
        UPDATE users SET first_name = ?, username = ? WHERE user_id = ?
    """, (user.first_name, user.username, user.id))
    conn.commit()

    cursor.execute("SELECT value FROM settings WHERE key = 'welcome_text'")
    res_text = cursor.fetchone()
    
    cursor.execute("SELECT value FROM settings WHERE key = 'logo'")
    res_logo = cursor.fetchone()
    conn.close()
    
    if lang == "ru":
        default_t = "Здравствуйте, {user_name}!\nДобро пожаловать в каталог современной мебели."
    else:
        default_t = "Assalomu alaykum, {user_name}!\nZamonaviy mebellar katalogiga xush kelibsiz."
        
    template = res_text[0] if res_text else default_t
    text = template.replace("{user_name}", user.first_name)
    logo_file_id = res_logo[0] if res_logo else None

    kb = main_menu_keyboard(lang)
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.message.delete()
        except:
            pass
        chat_id = query.message.chat_id
    else:
        chat_id = update.message.chat_id

    if logo_file_id:
        await context.bot.send_photo(chat_id=chat_id, photo=logo_file_id, caption=text, reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)

async def user_videos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    copyright_notice = "⚖️ **Mualliflik huquqi bo'yicha eslatma:**\nBotimizdagi videoroliklar internet tarmoqlaridan olingan bo'lib, ular tijorat maqsadida ishlatilmaydi. Barcha huquqlar o'z mualliflariga tegishli\n\n"
    
    if lang == "ru":
        copyright_notice = "⚖️ **Уведомление об авторских правах:**\nВидеоролики в нашем боте взяты из интернет-сети и не используются в коммерческих целях. Все права принадлежат их авторам\n\n"
        keyboard = [
            [InlineKeyboardButton("🛠 Лайфхаки для мастеров", callback_data="uwat_master_lifehacks_0")],
            [InlineKeyboardButton("💡 Советы и идеи (Цвет и Дизайн)", callback_data="uwat_design_ideas_0")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        caption_text = copyright_notice + "💡 Полезные видео и лайфхаки\n\nВыберите нужный раздел:"
    else:
        keyboard = [
            [InlineKeyboardButton("🛠 Ustalar uchun layfhaklar", callback_data="uwat_master_lifehacks_0")],
            [InlineKeyboardButton("💡 Maslahat va g'oyalar (Rang va Dizayn)", callback_data="uwat_design_ideas_0")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")]
        ]
        caption_text = copyright_notice + "💡 Foydali videolar va layfhaklar\n\nKerakli bo'limni tanlang:"
        
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def user_videos_list_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    page = int(data_parts[-1])
    cat = "_".join(data_parts[1:-1]) 
    
    lang = get_current_lang()
    back_text = "Назад" if lang == "ru" else "Orqaga"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type, description FROM videos WHERE category = ? ORDER BY id DESC", (cat,))
    videos = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"⬅️ {back_text}", callback_data="main_videos")]])

    if not videos:
        msg = "В этом разделе пока нет видео или материалов." if lang == "ru" else f"Hozircha bu bo'limda videolar yoki materiallar yo'q."
        await context.bot.send_message(chat_id=query.message.chat_id, text=msg, reply_markup=back_kb)
        return
        
    limit = 3 
    total_pages = (len(videos) + limit - 1) // limit
    
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0
        
    start_idx = page * limit
    end_idx = start_idx + limit
    page_videos = videos[start_idx:end_idx]
    
    for v in page_videos:
        file_id, f_type, desc = v[0], v[1], v[2]
        caption = desc if desc else ""
            
        if f_type == "video":
            await context.bot.send_video(chat_id=query.message.chat_id, video=file_id, caption=caption, parse_mode="HTML")
        elif f_type == "photo":
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=file_id, caption=caption, parse_mode="HTML")
        else:
            await context.bot.send_document(chat_id=query.message.chat_id, document=file_id, caption=caption, parse_mode="HTML")
            
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"• {i+1} •" if i == page else str(i+1)
        page_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"uwat_{cat}_{i}"))
        
    keyboard_layout = []
    chunk_size = 5
    for i in range(0, len(page_buttons), chunk_size):
        keyboard_layout.append(page_buttons[i:i + chunk_size])
        
    keyboard_layout.append([InlineKeyboardButton(f"⬅️ {back_text}", callback_data="main_videos")])
    
    copyright_notice = "⚖️ **Mualliflik huquqi bo'yicha eslatma:**\nBotimizdagi videoroliklar internet tarmoqlaridan olingan bo'lib, ular tijorat maqsadida ishlatilmaydi. Barcha huquqlar o'z mualliflariga tegishli\n\n"
    if lang == "ru":
        copyright_notice = "⚖️ **Уведомление об авторских правах:**\nВидеоролики в нашем боте взяты из интернет-сети и не используются в коммерческих целях. Все права принадлежат их авторам\n\n"

    page_text_label = "Sahifani tanlang:" if lang != "ru" else "Выберите страницу:"
    final_message_text = copyright_notice + page_text_label

    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=final_message_text, 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_layout)
    )

async def user_catalog_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("🛏 Спальня", callback_data="subcat_yotoqxona")],
            [InlineKeyboardButton("🍳 Кухня", switch_inline_query_current_chat="Katalog: Oshxona"),
             InlineKeyboardButton("🛋 Мягкая мебель", switch_inline_query_current_chat="Katalog: Yumshoq_mebel")],
            [InlineKeyboardButton("🚪 Прихожая", switch_inline_query_current_chat="Katalog: Koridor"),
             InlineKeyboardButton("📺 ТВ зона", switch_inline_query_current_chat="Katalog: TV_zona")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        caption_text = "Выберите категорию (нажмите на кнопку, чтобы открыть галерею):"
    else:
        keyboard = [
            [InlineKeyboardButton("🛏 Yotoqxona", callback_data="subcat_yotoqxona")],
            [InlineKeyboardButton("🍳 Oshxona", switch_inline_query_current_chat="Katalog: Oshxona"),
             InlineKeyboardButton("🛋 Yumshoq mebel", switch_inline_query_current_chat="Katalog: Yumshoq_mebel")],
            [InlineKeyboardButton("🚪 Koridor", switch_inline_query_current_chat="Katalog: Koridor"),
             InlineKeyboardButton("📺 TV zona", switch_inline_query_current_chat="Katalog: TV_zona")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")]
        ]
        caption_text = "Kategoriyani tanlang (galereyani ochish uchun tugmani bosing):"
        
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def user_yotoqxona_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("🛏 Спальня для взрослых", switch_inline_query_current_chat="Katalog: Kattalar_yotoqxonasi")],
            [InlineKeyboardButton("🧸 Детская спальня", switch_inline_query_current_chat="Katalog: Bolalar_yotoqxonasi")],
            [InlineKeyboardButton("🚪 Шкаф-купе / Гардероб", switch_inline_query_current_chat="Katalog: Shkaf_kupe_garderob")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main_catalog")]
        ]
        caption_text = "Выберите раздел спальни (нажмите для просмотра):"
    else:
        keyboard = [
            [InlineKeyboardButton("🛏 Kattalar yotoqxonasi", switch_inline_query_current_chat="Katalog: Kattalar_yotoqxonasi")],
            [InlineKeyboardButton("🧸 Bolalar yotoqxonasi", switch_inline_query_current_chat="Katalog: Bolalar_yotoqxonasi")],
            [InlineKeyboardButton("🚪 Shkaf kupe / Garderob", switch_inline_query_current_chat="Katalog: Shkaf_kupe_garderob")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_catalog")]
        ]
        caption_text = "Yotoqxona bo'limini tanlang (ko'rish uchun bosing):"
        
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def user_catalog_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    if data_parts[-1].isdigit():
        page = int(data_parts[-1])
        cat = "_".join(data_parts[1:-1])
    else:
        page = 0
        cat = "_".join(data_parts[1:])
    
    lang = get_current_lang()
    back_text = "Назад" if lang == "ru" else "Orqaga"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT description, photo FROM products WHERE category = ? ORDER BY id DESC", (cat,))
    products = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass

    if cat in ["Kattalar_yotoqxonasi", "Bolalar_yotoqxonasi", "Shkaf_kupe_garderob"]:
        back_callback = "subcat_yotoqxona"
    else:
        back_callback = "main_catalog"

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"⬅️ {back_text}", callback_data=back_callback)]])

    if not products:
        msg = "В этой категории пока нет товаров." if lang == "ru" else f"Hozircha bu bo'limda mahsulotlar yo'q."
        await context.bot.send_message(chat_id=query.message.chat_id, text=msg, reply_markup=back_kb)
        return
        
    limit = 5
    total_pages = (len(products) + limit - 1) // limit
    
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0
        
    start_idx = page * limit
    end_idx = start_idx + limit
    page_products = products[start_idx:end_idx]
    
    for p in page_products:
        desc, photo = p[0], p[1]
        caption = desc if desc else ""
            
        if photo:
            if caption:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML")
            else:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo)
        else:
            if caption:
                await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML", disable_web_page_preview=True)
            
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"• {i+1} •" if i == page else str(i+1)
        page_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"ucat_{cat}_{i}"))
        
    keyboard_layout = []
    chunk_size = 5
    for i in range(0, len(page_buttons), chunk_size):
        keyboard_layout.append(page_buttons[i:i + chunk_size])
        
    keyboard_layout.append([InlineKeyboardButton(f"⬅️ {back_text}", callback_data=back_callback)])
    
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text="Sahifani tanlang:" if lang != "ru" else "Выберите страницу:", 
        reply_markup=InlineKeyboardMarkup(keyboard_layout)
    )

async def user_colors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand_name FROM brands")
    brands = cursor.fetchall()
    conn.close()
    
    keyboard = []
    has_akril = False
    
    for b_id, b_name in brands:
        if b_name.startswith("Akril:"):
            has_akril = True
            continue
            
        keyboard.append([InlineKeyboardButton(f"🎨 {b_name}", switch_inline_query_current_chat=b_name)])
        
    if has_akril:
        keyboard.insert(0, [InlineKeyboardButton("🎨 Akril", callback_data="subcat_akril")])
        
    back_text_str = "Назад" if lang == "ru" else "Orqaga"
    keyboard.append([InlineKeyboardButton(f"⬅️ {back_text_str}", callback_data="back_to_main")])
    
    cap = "Выберите материал или бренд:" if lang == "ru" else "Kerakli material yoki brendni tanlang:"
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=cap, reply_markup=InlineKeyboardMarkup(keyboard))

async def user_akril_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    keyboard = [
        [InlineKeyboardButton("🎨 Kashtan", switch_inline_query_current_chat="Akril: Kashtan")],
        [InlineKeyboardButton("🎨 Kastaman", switch_inline_query_current_chat="Akril: Kastaman")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_colors")]
    ]
    
    cap = "Akril bo'limidan kerakli turini tanlang:" if lang != "ru" else "Выберите подраздел акрила:"
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=cap, reply_markup=InlineKeyboardMarkup(keyboard))


async def inline_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.inline_query.query.strip()
    
    if not query_text:
        await update.inline_query.answer([], cache_time=0)
        return

    offset_str = update.inline_query.offset
    offset = int(offset_str) if offset_str else 0
    limit = 50 

    conn = get_db_connection()
    cursor = conn.cursor()
    results = []

    # Katalog bo'limlari uchun (Galereya ko'rinishida)
    if query_text.startswith("Katalog:"):
        cat_name = query_text.replace("Katalog:", "").strip()
        cursor.execute(
            "SELECT id, description, photo FROM products "
            "WHERE category = ? AND photo IS NOT NULL AND photo != '' "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (cat_name, limit, offset)
        )
        rows = cursor.fetchall()

        for p_id, desc, photo in rows:
            caption = f"📂 <b>{cat_name.replace('_', ' ')}</b>"
            if desc:
                caption += f"\n\n{desc}"

            results.append(
                InlineQueryResultCachedPhoto(
                    id=f"prod_{p_id}",
                    photo_file_id=photo,
                    title=f"Mahsulot {p_id}",
                    caption=caption,
                    parse_mode="HTML"
                )
            )
            
    # Ranglar va Brendlar bo'limi uchun (Galereya ko'rinishida)
    else:
        if query_text:
            like = f"%{query_text}%"
            cursor.execute(
                "SELECT id, brand, color_name, photo FROM colors "
                "WHERE (brand LIKE ? OR color_name LIKE ?) AND photo IS NOT NULL AND photo != '' "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (like, like, limit, offset)
            )
        else:
            cursor.execute(
                "SELECT id, brand, color_name, photo FROM colors "
                "WHERE photo IS NOT NULL AND photo != '' "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        rows = cursor.fetchall()

        for c_id, brand, c_name, photo in rows:
            caption = f"🎨 <b>{brand}</b>"
            if c_name:
                caption += f"\n{c_name}"

            results.append(
                InlineQueryResultCachedPhoto(
                    id=f"color_{c_id}",
                    photo_file_id=photo,
                    title=c_name if c_name else f"{brand} (#{c_id})",
                    caption=caption,
                    parse_mode="HTML"
                )
            )

    conn.close()
    
    # Cheksiz varaqlash mantiqi (pastga tortganda keyingi 50 tasini qo'shish)
    next_offset = str(offset + limit) if len(rows) == limit else ""
    await update.inline_query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)

async def main_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'info'")
    res = cursor.fetchone()
    conn.close()
    
    if lang == "ru":
        text = res[0] if res else "📞 Контакты:\nТелефон: +998 90 123-45-67\nАдрес: г. Ташкент"
    else:
        text = res[0] if res else "📞 Biz bilan bog'lanish:\nTelefon: +998 90 123-45-67\nManzil: Toshkent shahar"
        
    back_text = "Назад" if lang == "ru" else "Orqaga"
    keyboard = [[InlineKeyboardButton(f"⬅️ {back_text}", callback_data="back_to_main")]]
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

async def main_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    back_text = "Назад" if lang == "ru" else "Orqaga"
    
    keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="set_lang_uz"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru")],
        [InlineKeyboardButton(f"⬅️ {back_text}", callback_data="back_to_main")]
    ]
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="Tilni tanlang / Выберите язык:", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    lang_code = query.data.split("_")[-1]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES ('language', ?)", (lang_code,))
    conn.commit()
    conn.close()
    _LANG_CACHE["value"] = lang_code
    
    if lang_code == "ru":
        text = "✅ Язык успешно изменен на русский!"
    else:
        text = "✅ Til muvaffaqiyatli o'zgartirildi!"
        
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=main_menu_keyboard(lang_code))

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    await start(update, context)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        lang = get_current_lang()
        deny_text = "⛔ Sizda admin panelga kirish huquqi yo'q." if lang != "ru" else "⛔ У вас нет доступа к панели администратора."
        if update.callback_query:
            await update.callback_query.answer(deny_text, show_alert=True)
        else:
            await update.message.reply_text(deny_text)
        return

    keyboard = [
        [InlineKeyboardButton("🖼 Logotipni o'zgartirish", callback_data="admin_logo"),
         InlineKeyboardButton("💬 Salomlashish matni", callback_data="admin_welcome")],
        [InlineKeyboardButton("⚙️ Ma'lumotlarni sozlash", callback_data="admin_settings"),
         InlineKeyboardButton("🎨 Brendlar va Ranglar", callback_data="admin_brands_menu")],
        [InlineKeyboardButton("➕ Yangi Mahsulot Qo'shish", callback_data="admin_add_prod"),
         InlineKeyboardButton("💡 Video va Layfhak Qo'shish", callback_data="admin_add_video_menu")],
        [InlineKeyboardButton("🗑 Rasmlarni O'chirish", callback_data="admin_del_prod_menu"),
         InlineKeyboardButton("🎬 Videolarni O'chirish", callback_data="admin_del_video_menu")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
         InlineKeyboardButton("📢 Xabar yuborish", callback_data="broadcast_start")],
        [InlineKeyboardButton("🆕 Yangilanish haqida xabar berish", callback_data="notify_update_confirm")],
        [InlineKeyboardButton("🗑 Oxirgi xabarni o'chirish", callback_data="broadcast_delete")],
        [InlineKeyboardButton("❌ Chiqish", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "👑 <b>Admin Panel</b>\nBoshqarish uchun kerakli tugmani tanlang:"
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.message.delete()
        except:
            pass
        chat_id = query.message.chat_id
    else:
        chat_id = update.message.chat_id

    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup)

async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    await admin_panel(update, context)

@admin_only
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]])
    text = (
        "📢 <b>Foydalanuvchilarga xabar yuborish (Rassilka)</b>\n\n"
        "Barcha ro'yxatdan o'tgan foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring "
        "(Matn, rasm, video yoki istalgan xabar turini yuborishingiz mumkin):"
    )
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode="HTML", reply_markup=reply_kb)
    return BROADCAST_TEXT

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_to_send = update.message
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM broadcast_history")
    conn.commit()

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    
    success_count = 0
    blocked_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text("⏳ Xabar foydalanuvchilarga yuborilmoqda, iltimos kuting...")
    
    for user in users:
        u_id = user[0]
        try:
            sent_msg = await message_to_send.copy(chat_id=u_id)
            cursor.execute("INSERT INTO broadcast_history (user_id, message_id) VALUES (?, ?)", (u_id, sent_msg.message_id))
            success_count += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                sent_msg = await message_to_send.copy(chat_id=u_id)
                cursor.execute("INSERT INTO broadcast_history (user_id, message_id) VALUES (?, ?)", (u_id, sent_msg.message_id))
                success_count += 1
            except Exception:
                fail_count += 1
        except Exception as e:
            err_str = str(e).lower()
            if "blocked" in err_str or "deactivated" in err_str or "bot was blocked" in err_str:
                blocked_count += 1
            else:
                fail_count += 1
        await asyncio.sleep(0.05)
                
    conn.commit()
    conn.close()
    
    result_text = (
        f"✅ <b>Rassilka yakunlandi!</b>\n\n"
        f"📤 Muvaffaqiyatli yuborildi: <b>{success_count} ta</b>\n"
        f"🚫 Botni bloklaganlar: <b>{blocked_count} ta</b>\n"
        f"⚠️ Xatolik yuz berdi: <b>{fail_count} ta</b>\n\n"
        f"<i>Agar xabarni hammadan o'chirmoqchi bo'lsangiz, Admin panelga o'tib 'Oxirgi xabarni o'chirish' tugmasini bosing.</i>"
    )
    
    lang = get_current_lang()
    await status_msg.edit_text(result_text, parse_mode="HTML", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

@admin_only
async def broadcast_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, message_id FROM broadcast_history")
    records = cursor.fetchall()
    
    deleted_count = 0
    for row in records:
        u_id, m_id = row[0], row[1]
        try:
            await context.bot.delete_message(chat_id=u_id, message_id=m_id)
            deleted_count += 1
        except Exception:
            pass 
            
    cursor.execute("DELETE FROM broadcast_history")
    conn.commit()
    conn.close()
    
    lang = get_current_lang()
    try:
        await query.message.delete()
    except:
        pass
        
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✅ Yuborilgan xabar {deleted_count} ta foydalanuvchidan muvaffaqiyatli o'chirildi!",
        reply_markup=main_menu_keyboard(lang)
    )

@admin_only
async def notify_update_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "🆕 <b>Yangilanish haqida xabar berish</b>\n\n"
        "Barcha obunachilarga botda yangilik (yangi bo'lim, mahsulot yoki video) "
        "qo'shilgani haqida xabar yuboriladi. Xabarda ularga <b>🔄 Botni yangilash</b> "
        "tugmasini bosishlari so'raladi.\n\n"
        "Yuborishni tasdiqlaysizmi?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ha, yuborish", callback_data="notify_update_send")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]
    ])
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode="HTML", reply_markup=kb)

@admin_only
async def notify_update_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_current_lang()
    if lang == "ru":
        notify_text = (
            "🆕 <b>Новость!</b>\n\n"
            "В боте появились новые разделы, товары или видео!\n"
            "Чтобы увидеть обновления, нажмите кнопку ниже 👇"
        )
        btn_text = "🔄 Обновить бот"
    else:
        notify_text = (
            "🆕 <b>Yangilik!</b>\n\n"
            "Botimizda yangi bo'lim, mahsulot yoki video qo'shildi!\n"
            "Yangiliklarni ko'rish uchun quyidagi tugmani bosing 👇"
        )
        btn_text = "🔄 Botni yangilash"

    notify_kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, callback_data="back_to_main")]])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    success_count = 0
    blocked_count = 0
    fail_count = 0

    try:
        await query.message.delete()
    except:
        pass
    status_msg = await context.bot.send_message(chat_id=query.message.chat_id, text="⏳ Xabar foydalanuvchilarga yuborilmoqda, iltimos kuting...")

    for user in users:
        u_id = user[0]
        try:
            await context.bot.send_message(chat_id=u_id, text=notify_text, parse_mode="HTML", reply_markup=notify_kb)
            success_count += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                await context.bot.send_message(chat_id=u_id, text=notify_text, parse_mode="HTML", reply_markup=notify_kb)
                success_count += 1
            except Exception:
                fail_count += 1
        except Exception as e:
            err_str = str(e).lower()
            if "blocked" in err_str or "deactivated" in err_str or "bot was blocked" in err_str:
                blocked_count += 1
            else:
                fail_count += 1
        await asyncio.sleep(0.05)

    result_text = (
        f"✅ <b>Yangilanish xabari yuborildi!</b>\n\n"
        f"📤 Muvaffaqiyatli yuborildi: <b>{success_count} ta</b>\n"
        f"🚫 Botni bloklaganlar: <b>{blocked_count} ta</b>\n"
        f"⚠️ Xatolik yuz berdi: <b>{fail_count} ta</b>"
    )
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin panelga qaytish", callback_data="back_to_admin")]])
    await status_msg.edit_text(result_text, parse_mode="HTML", reply_markup=back_kb)

@admin_only
async def admin_add_video_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛠 Ustalar uchun layfhaklar", callback_data="vcat_master_lifehacks")],
        [InlineKeyboardButton("💡 Maslahat va g'oyalar (Rang/Dizayn)", callback_data="vcat_design_ideas")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]
    ]
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="💡 Qaysi bo'limga video yoki rasm yuklamoqchisiz?:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_VIDEO_CAT

async def admin_add_video_cat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split("_", 1)[1] 
    context.user_data['video_cat'] = cat
    
    try:
        await query.message.delete()
    except:
        pass
        
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_add_video_menu")]])
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=f"Tanlangan bo'lim: <b>{cat}</b>\n\n🎬 Endi shu bo'lim uchun **Video**, **Rasm** yoki **Fayl** yuboring:", 
        parse_mode="HTML", 
        reply_markup=reply_kb
    )
    return ADD_VIDEO_FILE

async def admin_add_video_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        context.user_data['video_file_id'] = update.message.video.file_id
        context.user_data['video_file_type'] = "video"
    elif update.message.photo:
        context.user_data['video_file_id'] = update.message.photo[-1].file_id
        context.user_data['video_file_type'] = "photo"
    elif update.message.document:
        context.user_data['video_file_id'] = update.message.document.file_id
        context.user_data['video_file_type'] = "document"
    else:
        await update.message.reply_text("⚠️ Iltimos, video, rasm yoki fayl yuboring!")
        return ADD_VIDEO_FILE
        
    keyboard = [
        [InlineKeyboardButton("⏭ Matnsiz saqlash", callback_data="skip_video_desc")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_add_video_menu")]
    ]
    await update.message.reply_text(
        "📝 Video/material uchun izoh (matn) yuboring:\n(Masalan: foydali maslahat matni)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_VIDEO_DESC

async def admin_add_video_desc_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    cat = context.user_data.get('video_cat', 'master_lifehacks')
    file_id = context.user_data.get('video_file_id')
    file_type = context.user_data.get('video_file_type')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO videos (category, file_id, file_type, description) VALUES (?, ?, ?, ?)",
                   (cat, file_id, file_type, desc))
    conn.commit()
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("➕ Yana video qo'shish", callback_data=f"vcat_{cat}")],
        [InlineKeyboardButton("✅ Yakunlash (Admin panel)", callback_data="back_to_admin")]
    ]
    await update.message.reply_text("✅ Video muvaffaqiyatli saqlandi!", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_VIDEO_CAT

async def admin_add_video_desc_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = context.user_data.get('video_cat', 'master_lifehacks')
    file_id = context.user_data.get('video_file_id')
    file_type = context.user_data.get('video_file_type')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO videos (category, file_id, file_type, description) VALUES (?, ?, ?, ?)",
                   (cat, file_id, file_type, ""))
    conn.commit()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    keyboard = [
        [InlineKeyboardButton("➕ Yana video qo'shish", callback_data=f"vcat_{cat}")],
        [InlineKeyboardButton("✅ Yakunlash (Admin panel)", callback_data="back_to_admin")]
    ]
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Video muvaffaqiyatli saqlandi!", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_VIDEO_CAT

@admin_only
async def admin_welcome_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'welcome_text'")
    res = cursor.fetchone()
    current_text = res[0] if res else ""
    conn.close()
    
    msg = (
        "💬 <b>Salomlashish matnini tahrirlash</b>\n\n"
        f"Hozirgi matn:\n<code>{current_text}</code>\n\n"
        "Yangi matnni yuboring (Foydalanuvchi ismi chiqishi uchun matnga <b>{user_name}</b> so'zini qo'shib yuborishingiz mumkin):"
    )
    
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]])
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=msg, parse_mode="HTML", reply_markup=reply_kb)
    return SET_WELCOME

async def admin_welcome_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_text = update.message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES ('welcome_text', ?)", (new_text,))
    conn.commit()
    conn.close()
    lang = get_current_lang()
    await update.message.reply_text("✅ Salomlashish matni muvaffaqiyatli yangilandi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

@admin_only
async def admin_brands_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Yangi brend/bo'lim qo'shish", callback_data="abrand_add"),
         InlineKeyboardButton("🎨 Brendga rang/rasm qo'shish", callback_data="acolor_start")],
        [InlineKeyboardButton("✏️ Rang nomi/kodini o'zgartirish", callback_data="acolor_edit_start"),
         InlineKeyboardButton("🗑 Rang/rasmni o'chirish", callback_data="adelcolor_start")],
        [InlineKeyboardButton("🗑 Brendni o'chirish", callback_data="abrand_del")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]
    ]
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="🎨 <b>Brendlar va ranglarni boshqarish bo'limi:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

@admin_only
async def add_brand_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")]])
    text = "➕ Yangi brend yoki bo'lim nomini yuboring\n(masalan: <i>Akril: Kashtan</i> yoki <i>MDF Matte</i>):"
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_kb, parse_mode="HTML")
    return ADD_NEW_BRAND

async def add_brand_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    brand_name = update.message.text.strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO brands (brand_name) VALUES (?)", (brand_name,))
        conn.commit()
        lang = get_current_lang()
        await update.message.reply_text(f"✅ '{brand_name}' muvaffaqiyatli qo'shildi!", reply_markup=main_menu_keyboard(lang))
    except sqlite3.IntegrityError:
        lang = get_current_lang()
        await update.message.reply_text("⚠️ Bunday nomdagi brend allaqachon mavjud!", reply_markup=main_menu_keyboard(lang))
    conn.close()
    return ConversationHandler.END

@admin_only
async def del_brand_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand_name FROM brands")
    brands = cursor.fetchall()
    conn.close()
    
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")]])
    try:
        await query.message.delete()
    except:
        pass

    if not brands:
        await context.bot.send_message(chat_id=query.message.chat_id, text="O'chirish uchun brendlar yo'q.", reply_markup=back_kb)
        return ConversationHandler.END
        
    keyboard = []
    for b in brands:
        keyboard.append([InlineKeyboardButton(f"❌ {b[1]}", callback_data=f"delbrand_{b[0]}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")])
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="O'chirmoqchi bo'lgan brendni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEL_BRAND

async def del_brand_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    b_id = query.data.split("_")[1]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM brands WHERE id = ?", (b_id,))
    conn.commit()
    conn.close()
    
    lang = get_current_lang()
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Brend muvaffaqiyatli o'chirildi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

@admin_only
async def add_color_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand_name FROM brands")
    brands = cursor.fetchall()
    conn.close()
    
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")]])
    try:
        await query.message.delete()
    except:
        pass

    if not brands:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Avval brend yoki bo'lim qo'shishingiz kerak!", reply_markup=back_kb)
        return ConversationHandler.END
        
    keyboard = []
    row = []
    for b in brands:
        row.append(InlineKeyboardButton(b[1], callback_data=f"abrand_{b[0]}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")])
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="Qaysi material yoki brend uchun rang qo'shmoqchisiz?:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_BRAND_MENU

async def add_color_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    b_id = query.data.split("_")[1]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM brands WHERE id = ?", (b_id,))
    res = cursor.fetchone()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass

    if not res:
        lang = get_current_lang()
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik yuz berdi.", reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END
        
    brand_name = res[0]
    context.user_data['color_brand'] = brand_name
    
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="acolor_start")]])
    text = f"Tanlandi: {brand_name}\n\n📸 Endi material / rang namunasining rasmini yuboring:"
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_kb)
    return ADD_COLOR_PHOTO

async def add_color_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['color_photo'] = update.message.photo[-1].file_id
    
    keyboard = [
        [InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="skip_color_name")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="acolor_start")]
    ]
    await update.message.reply_text(
        "🎨 Rang nomi yoki kodini yuboring (masalan: #FFFFFF yoki W1000 ST9).\n"
        "Agar yozishni xohlamasangiz, o'tkazib yuborishingiz mumkin:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_COLOR_NAME

async def add_color_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c_name = update.message.text
    brand = context.user_data['color_brand']
    photo = context.user_data['color_photo']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO colors (brand, color_name, photo) VALUES (?, ?, ?)", (brand, c_name, photo))
    conn.commit()
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("➕ Yana rasm qo'shish", callback_data=f"abrand_{get_brand_id(brand)}")],
        [InlineKeyboardButton("✅ Yakunlash (Asosiy menyu)", callback_data="finish_adding_colors")]
    ]
    await update.message.reply_text("✅ Rang/material muvaffaqiyatli saqlandi! Yana rasm qo'shasizmi yoki yakunlaysizmi?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_COLOR_PHOTO

async def add_color_name_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    brand = context.user_data['color_brand']
    photo = context.user_data['color_photo']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO colors (brand, color_name, photo) VALUES (?, ?, ?)", (brand, "", photo))
    conn.commit()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    keyboard = [
        [InlineKeyboardButton("➕ Yana rasm qo'shish", callback_data=f"abrand_{get_brand_id(brand)}")],
        [InlineKeyboardButton("✅ Yakunlash (Asosiy menyu)", callback_data="finish_adding_colors")]
    ]
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Rang/material muvaffaqiyatli saqlandi! Yana rasm qo'shasizmi?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_COLOR_PHOTO

def get_brand_id(brand_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM brands WHERE brand_name = ?", (brand_name,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 1

@admin_only
async def admin_edit_color_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand_name FROM brands")
    brands = cursor.fetchall()
    conn.close()

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")]])
    try:
        await query.message.delete()
    except:
        pass

    if not brands:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Hali brend/bo'lim yo'q.", reply_markup=back_kb)
        return ConversationHandler.END

    keyboard = []
    row = []
    for b in brands:
        row.append(InlineKeyboardButton(b[1], callback_data=f"ecbrand_{b[0]}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")])

    await context.bot.send_message(chat_id=query.message.chat_id, text="Qaysi bo'limdagi rangni tahrirlaysiz?", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_COLOR_BRAND

async def admin_edit_color_pick_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    b_id = data_parts[1]
    page = int(data_parts[2]) if len(data_parts) > 2 else 0

    context.user_data['edit_brand_id'] = b_id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM brands WHERE id = ?", (b_id,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik yuz berdi.")
        return ConversationHandler.END

    brand_name = res[0]
    cursor.execute("SELECT id, color_name FROM colors WHERE brand = ? ORDER BY id DESC", (brand_name,))
    colors = cursor.fetchall()
    conn.close()

    try:
        await query.message.delete()
    except:
        pass

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="acolor_edit_start")]])
    if not colors:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"'{brand_name}' bo'limida hali rasm yo'q.", reply_markup=back_kb)
        return ConversationHandler.END

    limit = 10
    total_pages = (len(colors) + limit - 1) // limit
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0

    start_idx = page * limit
    end_idx = start_idx + limit
    page_colors = colors[start_idx:end_idx]

    keyboard = []
    for c_id, c_name in page_colors:
        label = c_name if c_name else f"#{c_id} (nomsiz)"
        keyboard.append([InlineKeyboardButton(f"✏️ {label}", callback_data=f"eccolor_{c_id}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"ecbrand_{b_id}_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"Sahifa: {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"ecbrand_{b_id}_{page+1}"))
        
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("⬅️ Orqaga (Brendlar)", callback_data="acolor_edit_start")])

    await context.bot.send_message(chat_id=query.message.chat_id, text=f"'{brand_name}' — tahrirlash uchun rangni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_COLOR_SELECT

async def admin_edit_color_pick_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    c_id = query.data.split("_")[1]
    context.user_data['edit_color_id'] = c_id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT brand, color_name, photo FROM colors WHERE id = ?", (c_id,))
    res = cursor.fetchone()
    conn.close()

    try:
        await query.message.delete()
    except:
        pass

    if not res:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik: rang topilmadi.")
        return ConversationHandler.END

    brand, c_name, photo = res
    cur_name = c_name if c_name else "(nomsiz)"
    text = f"Bo'lim: <b>{brand}</b>\nJoriy nom/kod: <b>{cur_name}</b>\n\n✏️ Yangi nom yoki kodni yozib yuboring:"

    if photo:
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=text, parse_mode="HTML")
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode="HTML")
    return EDIT_COLOR_NAME

async def admin_edit_color_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    c_id = context.user_data.get('edit_color_id')
    b_id = context.user_data.get('edit_brand_id')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE colors SET color_name = ? WHERE id = ?", (new_name, c_id))
    conn.commit()
    conn.close()

    keyboard = [
        [InlineKeyboardButton("✏️ Yana tahrirlash (Shu bo'limda)", callback_data=f"ecbrand_{b_id}_0")] if b_id else [],
        [InlineKeyboardButton("⬅️ Brendlar ro'yxatiga qaytish", callback_data="acolor_edit_start")],
        [InlineKeyboardButton("🏠 Admin panelga qaytish", callback_data="admin_brands_menu")]
    ]
    
    await update.message.reply_text(
        f"✅ Nom muvaffaqiyatli yangilandi: <b>{new_name}</b>\n\nQanday davom etamiz?", 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup([k for k in keyboard if k])
    )
    return EDIT_COLOR_BRAND

# --- RANGLARNI O'CHIRISH FUNKSIYALARI ---
@admin_only
async def admin_del_color_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand_name FROM brands")
    brands = cursor.fetchall()
    conn.close()

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")]])
    try:
        await query.message.delete()
    except:
        pass

    if not brands:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Hali brend/bo'lim yo'q.", reply_markup=back_kb)
        return

    keyboard = []
    row = []
    for b in brands:
        row.append(InlineKeyboardButton(b[1], callback_data=f"adelcview_{b[0]}_0"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_brands_menu")])

    await context.bot.send_message(chat_id=query.message.chat_id, text="Qaysi bo'limdagi ranglarni o'chirmoqchisiz?", reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def admin_del_color_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    b_id = int(data_parts[1])
    idx = int(data_parts[2])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM brands WHERE id = ?", (b_id,))
    brand_res = cursor.fetchone()
    
    if not brand_res:
        conn.close()
        return
        
    brand_name = brand_res[0]
    cursor.execute("SELECT id, color_name, photo FROM colors WHERE brand = ? ORDER BY id DESC", (brand_name,))
    colors = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga (Brendlar)", callback_data="adelcolor_start")]])

    if not colors:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"'{brand_name}' bo'limida o'chirish uchun ranglar yo'q.", reply_markup=back_kb)
        return
        
    if idx >= len(colors): idx = len(colors) - 1
    if idx < 0: idx = 0
        
    c = colors[idx]
    c_id, c_name, photo = c[0], c[1], c[2]
    
    cur_name = c_name if c_name else "(nomsiz)"
    caption = f"📄 <b>{idx+1} / {len(colors)}</b>\n🆔 <b>ID: {c_id}</b> | 📂 Bo'lim: <b>{brand_name}</b>\n🎨 Nomi/Kodi: <b>{cur_name}</b>"
        
    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"adelcview_{b_id}_{idx-1}"))
    
    nav_buttons.append(InlineKeyboardButton("❌ O'chirish", callback_data=f"adelcdel_{c_id}_{b_id}_{idx}"))
    
    if idx < len(colors) - 1:
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"adelcview_{b_id}_{idx+1}"))

    markup = InlineKeyboardMarkup([
        nav_buttons,
        [InlineKeyboardButton("⬅️ Orqaga (Brendlar)", callback_data="adelcolor_start")]
    ])
    
    if photo:
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML", reply_markup=markup)

@admin_only
async def admin_del_color_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    data_parts = query.data.split("_")
    c_id = int(data_parts[1])
    b_id = int(data_parts[2])
    idx = int(data_parts[3])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM colors WHERE id = ?", (c_id,))
    conn.commit()
    conn.close()
    
    try:
        await query.answer("✅ Rang o'chirildi!")
    except Exception:
        pass
        
    query.data = f"adelcview_{b_id}_{idx}"
    await admin_del_color_view(update, context)

async def finish_adding_colors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except:
        pass
    lang = get_current_lang()
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Barcha rasmlar yuklandi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

@admin_only
async def admin_logo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]])
    text = "🖼 Yangi logotip rasmini yuboring:"
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_kb)
    return SET_LOGO

async def admin_logo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = update.message.photo[-1].file_id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES ('logo', ?)", (photo_file,))
    conn.commit()
    conn.close()
    lang = get_current_lang()
    await update.message.reply_text("✅ Logotip muvaffaqiyatli yangilandi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

@admin_only
async def admin_settings_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]])
    text = "⚙️ Yangi bog'lanish matni va ma'lumotlarini kiriting (Masalan: telefon, manzil, mo'ljal):"
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_kb)
    return SET_INFO

async def admin_settings_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = update.message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES ('info', ?)", (info_text,))
    conn.commit()
    conn.close()
    lang = get_current_lang()
    await update.message.reply_text("✅ Aloqa ma'lumotlari muvaffaqiyatli yangilandi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    p_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM colors")
    c_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM brands")
    b_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    u_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM videos")
    v_count = cursor.fetchone()[0]
    conn.close()
    
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{u_count} ta</b>\n"
        f"📦 Jami mahsulotlar: {p_count} ta\n"
        f"🎨 Jami ranglar/materiallar: {c_count} ta\n"
        f"💡 Jami videolar/layfhaklar: {v_count} ta\n"
        f"📂 Jami brend/bo'limlar: {b_count} ta"
    )
    
    reply_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Foydalanuvchilar ro'yxati", callback_data="admin_users_list_0")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]
    ])
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode="HTML", reply_markup=reply_kb)

@admin_only
async def admin_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    page = int(query.data.split("_")[-1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, username, joined_date FROM users ORDER BY joined_date DESC")
    users = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga (Statistika)", callback_data="admin_stats")]])

    if not users:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Hozircha botda foydalanuvchilar yo'q.", reply_markup=back_kb)
        return
        
    limit = 10
    total_pages = (len(users) + limit - 1) // limit
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0
        
    start_idx = page * limit
    end_idx = start_idx + limit
    page_users = users[start_idx:end_idx]
    
    text = f"📋 <b>Bot foydalanuvchilari (Jami: {len(users)} ta)</b>\n<i>Sahifa: {page+1} / {total_pages}</i>\n\n"
    
    for idx, u in enumerate(page_users, start=start_idx+1):
        uid, fname, uname, j_date = u[0], u[1], u[2], u[3]
        safe_name = fname.replace("<", "&lt;").replace(">", "&gt;") if fname else "Noma'lum"
        username_str = f"@{uname}" if uname else "<i>username yo'q</i>"
        text += f"{idx}. <b>{safe_name}</b> ({username_str})\n   ID: <code>{uid}</code> | 📅 {j_date}\n\n"
        
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"• {i+1} •" if i == page else str(i+1)
        page_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"admin_users_list_{i}"))
        
    keyboard_layout = []
    chunk_size = 5
    for i in range(0, len(page_buttons), chunk_size):
        keyboard_layout.append(page_buttons[i:i + chunk_size])
        
    keyboard_layout.append([InlineKeyboardButton("⬅️ Orqaga (Statistika)", callback_data="admin_stats")])
    
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(keyboard_layout),
        disable_web_page_preview=True
    )

@admin_only
async def admin_add_prod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛏 Yotoqxona (Barchasi)", callback_data="acat_yotoqxona_menu")],
        [InlineKeyboardButton("🍳 Oshxona", callback_data="cat_Oshxona"),
         InlineKeyboardButton("🛋 Yumshoq mebel", callback_data="cat_Yumshoq_mebel")],
        [InlineKeyboardButton("🚪 Koridor", callback_data="cat_Koridor"),
         InlineKeyboardButton("📺 TV zona", callback_data="cat_TV_zona")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]
    ]
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="Mahsulot qo'shish uchun kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_CAT

async def admin_add_prod_yotoqxona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🛏 Kattalar yotoqxonasi", callback_data="cat_Kattalar_yotoqxonasi")],
        [InlineKeyboardButton("🧸 Bolalar yotoqxonasi", callback_data="cat_Bolalar_yotoqxonasi")],
        [InlineKeyboardButton("🚪 Shkaf kupe / Garderob", callback_data="cat_Shkaf_kupe_garderob")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_add_prod_back")]
    ]
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="Yotoqxona turini tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_CAT

async def admin_add_prod_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await admin_add_prod(update, context)

async def add_prod_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("cat_TV_zona"):
        cat = "TV_zona"
    elif query.data.startswith("cat_Yumshoq_mebel"):
        cat = "Yumshoq_mebel"
    elif query.data.startswith("cat_Kattalar_yotoqxonasi"):
        cat = "Kattalar_yotoqxonasi"
    elif query.data.startswith("cat_Bolalar_yotoqxonasi"):
        cat = "Bolalar_yotoqxonasi"
    elif query.data.startswith("cat_Shkaf_kupe_garderob"):
        cat = "Shkaf_kupe_garderob"
    else:
        cat = query.data.split("_")[1]
        
    context.user_data['prod_cat'] = cat
    
    try:
        await query.message.delete()
    except:
        pass

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_add_prod")]])
    text = f"Tanlangan kategoriya: <b>{cat}</b>\n\n📸 Endi shu kategoriya uchun rasm yuboring:"
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)
    return ADD_PHOTO

async def add_prod_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ Iltimos, matn emas, aynan **rasm** yuboring!")
        return ADD_PHOTO
        
    context.user_data['prod_photo'] = update.message.photo[-1].file_id
    
    keyboard = [
        [InlineKeyboardButton("⏭ O'tkazib yuborish (Matnsiz)", callback_data="skip_desc")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_add_prod")]
    ]
    await update.message.reply_text(
        "📝 Mahsulot uchun ixtiyoriy matn yuboring (masalan: nomi, narxi, o'lchami).\n"
        "Agar matn yozishni xohlamasangiz, quyidagi tugmani bosing:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_DESC

async def add_prod_desc_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    cat = context.user_data.get('prod_cat', 'Boshqa')
    photo = context.user_data['prod_photo']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (category, title, description, photo) VALUES (?, ?, ?, ?)",
                   (cat, "", desc, photo))
    conn.commit()
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("➕ Yana rasm qo'shish", callback_data=f"cat_{cat}")],
        [InlineKeyboardButton("✅ Yakunlash (Asosiy menyu)", callback_data="finish_adding_products")]
    ]
    await update.message.reply_text("✅ Mahsulot muvaffaqiyatli saqlandi! Yana rasm qo'shasizmi?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_PHOTO

async def add_prod_desc_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = context.user_data.get('prod_cat', 'Boshqa')
    photo = context.user_data['prod_photo']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (category, title, description, photo) VALUES (?, ?, ?, ?)",
                   (cat, "", "", photo))
    conn.commit()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    keyboard = [
        [InlineKeyboardButton("➕ Yana rasm qo'shish", callback_data=f"cat_{cat}")],
        [InlineKeyboardButton("✅ Yakunlash (Asosiy menyu)", callback_data="finish_adding_products")]
    ]
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Mahsulot muvaffaqiyatli saqlandi! Yana rasm qo'shasizmi?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_PHOTO

async def finish_adding_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except:
        pass
    lang = get_current_lang()
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Barcha mahsulotlar yuklandi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

@admin_only
async def admin_del_prod_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🛏 Kattalar yotoqxonasi", callback_data="adelcat_Kattalar_yotoqxonasi_0"),
         InlineKeyboardButton("🧸 Bolalar yotoqxonasi", callback_data="adelcat_Bolalar_yotoqxonasi_0")],
        [InlineKeyboardButton("🚪 Shkaf kupe / Garderob", callback_data="adelcat_Shkaf_kupe_garderob_0"),
         InlineKeyboardButton("🍳 Oshxona", callback_data="adelcat_Oshxona_0")],
        [InlineKeyboardButton("🛋 Yumshoq mebel", callback_data="adelcat_Yumshoq_mebel_0"),
         InlineKeyboardButton("🚪 Koridor", callback_data="adelcat_Koridor_0")],
        [InlineKeyboardButton("📺 TV zona", callback_data="adelcat_TV_zona_0")]
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga (Admin panel)", callback_data="back_to_admin")])
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text="🗑 <b>Rasmlarni o'chirish</b>\nQaysi bo'limdagi rasmlarni o'chirmoqchisiz?", 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@admin_only
async def admin_del_cat_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    idx = int(data_parts[-1])
    cat = "_".join(data_parts[1:-1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, photo FROM products WHERE category = ? ORDER BY id DESC", (cat,))
    products = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga (Bo'limlar)", callback_data="admin_del_prod_menu")]])

    if not products:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Bu bo'limda o'chirish uchun mahsulotlar yo'q.", reply_markup=back_kb)
        return
        
    if idx >= len(products): idx = len(products) - 1
    if idx < 0: idx = 0
        
    p = products[idx]
    prod_id, desc, photo = p[0], p[1], p[2]
    
    caption = f"📄 <b>{idx+1} / {len(products)}</b>\n🆔 <b>ID: {prod_id}</b> | 📂 Bo'lim: <b>{cat}</b>"
    if desc:
        caption += f"\n\n{desc}"
        
    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"adelcat_{cat}_{idx-1}"))
    
    nav_buttons.append(InlineKeyboardButton("❌ O'chirish", callback_data=f"adelprod_del_{cat}_{prod_id}_{idx}"))
    
    if idx < len(products) - 1:
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"adelcat_{cat}_{idx+1}"))

    markup = InlineKeyboardMarkup([
        nav_buttons,
        [InlineKeyboardButton("⬅️ Orqaga (Bo'limlar)", callback_data="admin_del_prod_menu")]
    ])
    
    if photo:
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML", reply_markup=markup)

@admin_only
async def admin_del_prod_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    data_parts = query.data.split("_")
    current_idx = int(data_parts[-1])
    prod_id = int(data_parts[-2])
    cat = "_".join(data_parts[2:-2])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    
    try:
        await query.answer("✅ Mahsulot o'chirildi!")
    except Exception:
        pass
        
    query.data = f"adelcat_{cat}_{current_idx}"
    await admin_del_cat_view(update, context)

@admin_only
async def admin_del_video_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🛠 Ustalar uchun layfhaklar", callback_data="adelvcat_master_lifehacks_0")],
        [InlineKeyboardButton("💡 Maslahat va g'oyalar (Rang/Dizayn)", callback_data="adelvcat_design_ideas_0")],
        [InlineKeyboardButton("⬅️ Orqaga (Admin panel)", callback_data="back_to_admin")]
    ]
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text="🎬 <b>Videolarni o'chirish</b>\nQaysi bo'limdagi videolarni o'chirmoqchisiz?", 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@admin_only
async def admin_del_video_cat_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    idx = int(data_parts[-1])
    cat = "_".join(data_parts[1:-1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_id, file_type, description FROM videos WHERE category = ? ORDER BY id DESC", (cat,))
    videos = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga (Video bo'limlari)", callback_data="admin_del_video_menu")]])

    if not videos:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Bu bo'limda o'chirish uchun videolar yo'q.", reply_markup=back_kb)
        return
        
    if idx >= len(videos): idx = len(videos) - 1
    if idx < 0: idx = 0
        
    v = videos[idx]
    v_id, file_id, f_type, desc = v[0], v[1], v[2], v[3]
    
    caption = f"📄 <b>{idx+1} / {len(videos)}</b>\n🆔 <b>ID: {v_id}</b> | 📂 Bo'lim: <b>{cat}</b>"
    if desc:
        caption += f"\n\n{desc}"
        
    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"adelvcat_{cat}_{idx-1}"))
    
    nav_buttons.append(InlineKeyboardButton("❌ O'chirish", callback_data=f"adelv_del_{cat}_{v_id}_{idx}"))
    
    if idx < len(videos) - 1:
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"adelvcat_{cat}_{idx+1}"))

    markup = InlineKeyboardMarkup([
        nav_buttons,
        [InlineKeyboardButton("⬅️ Orqaga (Video bo'limlari)", callback_data="admin_del_video_menu")]
    ])
    
    if f_type == "video":
        await context.bot.send_video(chat_id=query.message.chat_id, video=file_id, caption=caption, parse_mode="HTML", reply_markup=markup)
    elif f_type == "photo":
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=file_id, caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        await context.bot.send_document(chat_id=query.message.chat_id, document=file_id, caption=caption, parse_mode="HTML", reply_markup=markup)

@admin_only
async def admin_del_video_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    data_parts = query.data.split("_")
    current_idx = int(data_parts[-1])
    v_id = int(data_parts[-2])
    cat = "_".join(data_parts[2:-2])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM videos WHERE id = ?", (v_id,))
    conn.commit()
    conn.close()
    
    try:
        await query.answer("✅ Video o'chirildi!")
    except Exception:
        pass
        
    query.data = f"adelvcat_{cat}_{current_idx}"
    await admin_del_video_cat_view(update, context)

async def noop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_current_lang()
    if update.callback_query:
        await update.callback_query.answer()
        await admin_panel(update, context)
    elif update.message:
        await update.message.reply_text("Amaliyot bekor qilindi.", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

if __name__ == "__main__":
    application = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(300)
        .write_timeout(300)
        .connect_timeout(300)
        .pool_timeout(300)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$"))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_users_list, pattern="^admin_users_list_"))
    application.add_handler(CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$"))
    application.add_handler(CallbackQueryHandler(noop_handler, pattern="^noop$"))
    application.add_handler(InlineQueryHandler(inline_search_handler))
    
    application.add_handler(CallbackQueryHandler(broadcast_delete, pattern="^broadcast_delete$"))
    application.add_handler(CallbackQueryHandler(notify_update_confirm, pattern="^notify_update_confirm$"))
    application.add_handler(CallbackQueryHandler(notify_update_send, pattern="^notify_update_send$"))

    logo_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_logo_start, pattern="^admin_logo$")],
        states={SET_LOGO: [MessageHandler(filters.PHOTO, admin_logo_save)]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")]
    )
    application.add_handler(logo_handler)

    welcome_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_welcome_start, pattern="^admin_welcome$")],
        states={SET_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_welcome_save)]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")]
    )
    application.add_handler(welcome_handler)

    settings_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_settings_start, pattern="^admin_settings$")],
        states={SET_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_settings_save)]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")]
    )
    application.add_handler(settings_handler)

    add_brand_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_brand_start, pattern="^abrand_add$")],
        states={DEL_BRAND: [CallbackQueryHandler(del_brand_execute, pattern="^delbrand_")], ADD_NEW_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_brand_save)]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")]
    )
    application.add_handler(add_brand_handler)

    del_brand_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(del_brand_start, pattern="^abrand_del$")],
        states={DEL_BRAND: [CallbackQueryHandler(del_brand_execute, pattern="^delbrand_")]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")]
    )
    application.add_handler(del_brand_handler)

    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="^broadcast_start$")],
        states={
            BROADCAST_TEXT: [
                MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_send),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")]
    )
    application.add_handler(broadcast_handler)

    add_video_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_video_menu, pattern="^admin_add_video_menu$")],
        states={
            ADD_VIDEO_CAT: [
                CallbackQueryHandler(admin_add_video_cat_selected, pattern="^vcat_"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ],
            ADD_VIDEO_FILE: [
                MessageHandler(filters.VIDEO | filters.PHOTO | filters.Document.ALL, admin_add_video_file),
                CallbackQueryHandler(admin_add_video_menu, pattern="^admin_add_video_menu$"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ],
            ADD_VIDEO_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_video_desc_text),
                CallbackQueryHandler(admin_add_video_desc_skip, pattern="^skip_video_desc$"),
                CallbackQueryHandler(admin_add_video_menu, pattern="^admin_add_video_menu$"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")]
    )
    application.add_handler(add_video_handler)

    add_color_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_color_start, pattern="^acolor_start$")],
        states={
            ADD_BRAND_MENU: [CallbackQueryHandler(add_color_brand, pattern="^abrand_")],
            ADD_COLOR_PHOTO: [
                MessageHandler(filters.PHOTO, add_color_photo),
                CallbackQueryHandler(add_color_brand, pattern="^abrand_"),
                CallbackQueryHandler(finish_adding_colors, pattern="^finish_adding_colors$"),
                CallbackQueryHandler(add_color_start, pattern="^acolor_start$")
            ],
            ADD_COLOR_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_color_name_text),
                CallbackQueryHandler(add_color_name_skip, pattern="^skip_color_name$"),
                CallbackQueryHandler(add_color_start, pattern="^acolor_start$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")]
    )
    application.add_handler(add_color_handler)

    edit_color_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_color_start, pattern="^acolor_edit_start$")],
        states={
            EDIT_COLOR_BRAND: [
                CallbackQueryHandler(admin_edit_color_pick_brand, pattern="^ecbrand_"),
                CallbackQueryHandler(admin_edit_color_start, pattern="^acolor_edit_start$"),
                CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")
            ],
            EDIT_COLOR_SELECT: [
                CallbackQueryHandler(admin_edit_color_pick_color, pattern="^eccolor_"),
                CallbackQueryHandler(admin_edit_color_start, pattern="^acolor_edit_start$")
            ],
            EDIT_COLOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_color_save)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")]
    )
    application.add_handler(edit_color_handler)

    add_product_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_prod, pattern="^admin_add_prod$")],
        states={
            ADD_CAT: [
                CallbackQueryHandler(admin_add_prod_yotoqxona, pattern="^acat_yotoqxona_menu$"),
                CallbackQueryHandler(admin_add_prod_back_handler, pattern="^admin_add_prod_back$"),
                CallbackQueryHandler(add_prod_cat, pattern="^cat_"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, add_prod_photo),
                CallbackQueryHandler(add_prod_cat, pattern="^cat_"),
                CallbackQueryHandler(finish_adding_products, pattern="^finish_adding_products$"),
                CallbackQueryHandler(admin_add_prod, pattern="^admin_add_prod$"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ],
            ADD_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_prod_desc_text),
                CallbackQueryHandler(add_prod_desc_skip, pattern="^skip_desc$"),
                CallbackQueryHandler(admin_add_prod, pattern="^admin_add_prod$"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")]
    )
    application.add_handler(add_product_handler)

    application.add_handlers([
        CallbackQueryHandler(admin_del_color_start, pattern="^adelcolor_start$"),
        CallbackQueryHandler(admin_del_color_view, pattern="^adelcview_"),
        CallbackQueryHandler(admin_del_color_execute, pattern="^adelcdel_"),

        CallbackQueryHandler(admin_del_prod_menu, pattern="^admin_del_prod_menu$"),
        CallbackQueryHandler(admin_del_cat_view, pattern="^adelcat_"),
        CallbackQueryHandler(admin_del_prod_execute, pattern="^adelprod_del_"),
        
        CallbackQueryHandler(admin_del_video_menu, pattern="^admin_del_video_menu$"),
        CallbackQueryHandler(admin_del_video_cat_view, pattern="^adelvcat_"),
        CallbackQueryHandler(admin_del_video_execute, pattern="^adelv_del_"),
        
        CallbackQueryHandler(user_catalog_menu, pattern="^main_catalog$"),
        CallbackQueryHandler(user_yotoqxona_submenu, pattern="^subcat_yotoqxona$"),
        CallbackQueryHandler(user_catalog_click, pattern="^ucat_"),
        CallbackQueryHandler(user_colors_menu, pattern="^main_colors$"),
        CallbackQueryHandler(user_akril_submenu, pattern="^subcat_akril$"),
        
        CallbackQueryHandler(user_videos_menu, pattern="^main_videos$"),
        CallbackQueryHandler(user_videos_list_click, pattern="^uwat_"),

        CallbackQueryHandler(main_info, pattern="^main_info$"),
        CallbackQueryHandler(main_lang, pattern="^main_lang$"),
        CallbackQueryHandler(set_lang, pattern="^set_lang_"),
        CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
    ])
    
    keep_alive()
    
    print("Bot muvaffaqiyatli ishga tushdi...")
    application.run_polling()
