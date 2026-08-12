from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot ishlayapti!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "8722268472:AAEgcBPD0m1jWjP_5WjXN9z080U9v2BT20c"
MANAGER_USERNAME = "azizbek_mebel"

# --- RENDER DATA DISK YO'LI ---
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

(
    ADD_CAT, ADD_PHOTO, ADD_DESC, 
    ADD_BRAND_MENU, ADD_NEW_BRAND, ADD_COLOR_PHOTO, ADD_COLOR_NAME,
    SET_LOGO, SET_INFO, SET_WELCOME, DEL_BRAND, EDIT_COLOR_NAME,
    ADD_VIDEO_CAT, ADD_VIDEO_FILE, ADD_VIDEO_DESC
) = range(15)

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT,
            color_name TEXT,
            photo TEXT
        )
    """)
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
    # Videolar uchun baza jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            file_id TEXT,
            file_type TEXT,
            description TEXT
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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'language'")
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else "uz"
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

# --- VIDEOLAR BO'LIMI (FOYDALANUCHI UCHUN) ---
async def user_videos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("🛠 Лайфхаки для мастеров", callback_data="uwat_master_lifehacks_0")],
            [InlineKeyboardButton("💡 Советы и идеи (Цвет и Дизайн)", callback_data="uwat_design_ideas_0")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        caption_text = "💡 Полезные видео и лайфхаки\n\nВыберите нужный раздел:"
    else:
        keyboard = [
            [InlineKeyboardButton("🛠 Ustalar uchun layfhaklar", callback_data="uwat_master_lifehacks_0")],
            [InlineKeyboardButton("💡 Maslahat va g'oyalar (Rang va Dizayn)", callback_data="uwat_design_ideas_0")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")]
        ]
        caption_text = "💡 Foydali videolar va layfhaklar\n\nKerakli bo'limni tanlang:"
        
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def user_videos_list_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    page = int(data_parts[-1])
    cat = "_".join(data_parts[1:-1]) # master_lifehacks yoki design_ideas
    
    lang = get_current_lang()
    back_text = "Назад" if lang == "ru" else "Orqaga"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type, description FROM videos WHERE category = ?", (cat,))
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
        
    limit = 3 # Videolar katta bo'lgani uchun bitta sahifaga 3 tadan chiqargani maqul
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
    
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text="Sahifani tanlang:" if lang != "ru" else "Выберите страницу:", 
        reply_markup=InlineKeyboardMarkup(keyboard_layout)
    )

async def user_catalog_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("🛏 Спальня", callback_data="subcat_yotoqxona")],
            [InlineKeyboardButton("🍳 Кухня", callback_data="ucat_Oshxona_0"),
             InlineKeyboardButton("🛋 Мягкая мебель", callback_data="ucat_Yumshoq_mebel_0")],
            [InlineKeyboardButton("🚪 Прихожая", callback_data="ucat_Koridor_0"),
             InlineKeyboardButton("📺 ТВ зона", callback_data="ucat_TV_zona_0")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        caption_text = "Выберите категорию:"
    else:
        keyboard = [
            [InlineKeyboardButton("🛏 Yotoqxona", callback_data="subcat_yotoqxona")],
            [InlineKeyboardButton("🍳 Oshxona", callback_data="ucat_Oshxona_0"),
             InlineKeyboardButton("🛋 Yumshoq mebel", callback_data="ucat_Yumshoq_mebel_0")],
            [InlineKeyboardButton("🚪 Koridor", callback_data="ucat_Koridor_0"),
             InlineKeyboardButton("📺 TV zona", callback_data="ucat_TV_zona_0")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")]
        ]
        caption_text = "Kategoriyani tanlang:"
        
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
            [InlineKeyboardButton("🛏 Спальня для взрослых", callback_data="ucat_Kattalar_yotoqxonasi_0")],
            [InlineKeyboardButton("🧸 Детская спальня", callback_data="ucat_Bolalar_yotoqxonasi_0")],
            [InlineKeyboardButton("🚪 Шкаф-купе / Гардероб", callback_data="ucat_Shkaf_kupe_garderob_0")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main_catalog")]
        ]
        caption_text = "Выберите раздел спальни:"
    else:
        keyboard = [
            [InlineKeyboardButton("🛏 Kattalar yotoqxonasi", callback_data="ucat_Kattalar_yotoqxonasi_0")],
            [InlineKeyboardButton("🧸 Bolalar yotoqxonasi", callback_data="ucat_Bolalar_yotoqxonasi_0")],
            [InlineKeyboardButton("🚪 Shkaf kupe / Garderob", callback_data="ucat_Shkaf_kupe_garderob_0")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_catalog")]
        ]
        caption_text = "Yotoqxona bo'limini tanlang:"
        
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
    cursor.execute("SELECT description, photo FROM products WHERE category = ?", (cat,))
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
            
        safe_b_name = b_name.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '').replace(':', '').replace('__', '_')
        keyboard.append([InlineKeyboardButton(f"🎨 {b_name}", callback_data=f"ucol_{safe_b_name}_0")])
        
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
        [InlineKeyboardButton("🎨 Kashtan", callback_data="ucol_Akril_Kashtan_0")],
        [InlineKeyboardButton("🎨 Kastaman", callback_data="ucol_Akril_Kastaman_0")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_colors")]
    ]
    
    cap = "Akril bo'limidan kerakli turini tanlang:" if lang != "ru" else "Выберите подраздел акрила:"
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=cap, reply_markup=InlineKeyboardMarkup(keyboard))

async def user_color_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    data_parts = query.data.split("_")
    page = int(data_parts[-1])
    brand_clean_query = "_".join(data_parts[1:-1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM brands")
    brands = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    selected_brand = None
    for b in brands:
        clean_b = b.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '').replace(':', '').replace('__', '_')
        if clean_b == brand_clean_query or b.replace(' ', '_') == brand_clean_query:
            selected_brand = b
            break
            
    if not selected_brand and brands:
        for b in brands:
            if brand_clean_query in b or b in brand_clean_query:
                selected_brand = b
                break

    try:
        await query.message.delete()
    except:
        pass

    if not selected_brand:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik: Brend topilmadi.", reply_markup=main_menu_keyboard(lang))
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT color_name, photo FROM colors WHERE brand = ?", (selected_brand,))
    colors = cursor.fetchall()
    conn.close()
    
    back_callback = "subcat_akril" if "Akril" in selected_brand else "main_colors"
    back_text_str = "Назад" if lang == "ru" else "Orqaga"
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(back_text_str, callback_data=back_callback)]])
    
    if not colors:
        msg = f"Для раздела '{selected_brand}' цвета еще не добавлены." if lang == "ru" else f"'{selected_brand}' bo'limi uchun ranglar hali kiritilmagan."
        await context.bot.send_message(chat_id=query.message.chat_id, text=msg, reply_markup=back_kb)
        return
        
    limit = 5
    total_pages = (len(colors) + limit - 1) // limit
    
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0
        
    start_idx = page * limit
    end_idx = start_idx + limit
    page_colors = colors[start_idx:end_idx]

    for c in page_colors:
        c_name, photo = c[0], c[1]
        caption = f"🎨 Раздел: <b>{selected_brand}</b>" if lang == "ru" else f"🎨 Bo'lim: <b>{selected_brand}</b>"
        if c_name:
            caption += f"\nКод/Название: <b>{c_name}</b>" if lang == "ru" else f"\nRang nomi/kodi: <b>{c_name}</b>"
            
        if photo:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML")
            
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"• {i+1} •" if i == page else str(i+1)
        page_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"ucol_{brand_clean_query}_{i}"))
        
    keyboard_layout = []
    chunk_size = 5
    for i in range(0, len(page_buttons), chunk_size):
        keyboard_layout.append(page_buttons[i:i + chunk_size])
        
    keyboard_layout.append([InlineKeyboardButton(back_text_str, callback_data=back_callback)])
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="Sahifani tanlang:" if lang != "ru" else "Выберите страницу:", reply_markup=InlineKeyboardMarkup(keyboard_layout))

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
    keyboard = [
        [InlineKeyboardButton("🖼 Logotipni o'zgartirish", callback_data="admin_logo"),
         InlineKeyboardButton("💬 Salomlashish matni", callback_data="admin_welcome")],
        [InlineKeyboardButton("⚙️ Ma'lumotlarni sozlash", callback_data="admin_settings"),
         InlineKeyboardButton("🎨 Brendlar va Ranglar", callback_data="admin_brands_menu")],
        [InlineKeyboardButton("➕ Yangi Mahsulot Qo'shish", callback_data="admin_add_prod"),
         InlineKeyboardButton("💡 Video va Layfhak Qo'shish", callback_data="admin_add_video_menu")],
        [InlineKeyboardButton("🗑 Rasmlarni O'chirish", callback_data="admin_del_prod_menu"),
         InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
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

# --- ADMIN: VIDEO QO'SHISH FUNKSIYALARI ---
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
    cat = query.data.split("_", 1)[1] # master_lifehacks yoki design_ideas
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

async def admin_brands_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Yangi brend/bo'lim qo'shish", callback_data="abrand_add"),
         InlineKeyboardButton("🎨 Brendga rang/rasm qo'shish", callback_data="acolor_start")],
        [InlineKeyboardButton("🗑 Brendni o'chirish", callback_data="abrand_del")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]
    ]
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="🎨 <b>Brendlar va ranglarni boshqarish bo'limi:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

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
    photo = context.user_data.get('prod_photo')
    
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
    photo = context.user_data.get('prod_photo')
    
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
        [InlineKeyboardButton("📺 TV zona", callback_data="adelcat_TV_zona_0")],
        [InlineKeyboardButton("🎨 Ranglar / Brendlar bo'limidan o'chirish", callback_data="adel_colors_select_brand")]
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

async def admin_del_cat_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    page = int(data_parts[-1])
    cat = "_".join(data_parts[1:-1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, photo FROM products WHERE category = ?", (cat,))
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
        prod_id, desc, photo = p[0], p[1], p[2]
        caption = f"🆔 <b>ID: {prod_id}</b> | 📂 Bo'lim: <b>{cat}</b>"
        if desc:
            caption += f"\n{desc}"
            
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❌ O'chirish", callback_data=f"adelprod_del_{cat}_{prod_id}_{page}")
            ]
        ])
        
        if photo:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=markup)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML", reply_markup=markup)
            
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"• {i+1} •" if i == page else str(i+1)
        page_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"adelcat_{cat}_{i}"))
        
    keyboard_layout = []
    chunk_size = 5
    for i in range(0, len(page_buttons), chunk_size):
        keyboard_layout.append(page_buttons[i:i + chunk_size])
        
    keyboard_layout.append([InlineKeyboardButton("⬅️ Orqaga (Bo'limlar)", callback_data="admin_del_prod_menu")])
    
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=f"📄 Sahifani tanlang (Jami: {len(products)} ta mahsulot):", 
        reply_markup=InlineKeyboardMarkup(keyboard_layout)
    )

async def admin_del_prod_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    data_parts = query.data.split("_")
    cat = data_parts[2]
    prod_id = data_parts[3]
    current_page = int(data_parts[4])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    
    try:
        await query.message.delete()
        await query.answer("Mahsulot o'chirildi!")
    except Exception as e:
        await query.answer("Mahsulot o'chirildi!", show_alert=False)
        
    query.data = f"adelcat_{cat}_{current_page}"
    await admin_del_cat_view(update, context)

async def admin_del_colors_select_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand_name FROM brands")
    brands = cursor.fetchall()
    conn.close()
    
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_del_prod_menu")]])
    try:
        await query.message.delete()
    except:
        pass

    if not brands:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Brendlar topilmadi.", reply_markup=back_kb)
        return
        
    keyboard = []
    for b in brands:
        keyboard.append([InlineKeyboardButton(f"🎨 {b[1]}", callback_data=f"adelcolcat_{b[1]}_0")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_del_prod_menu")])
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="Qaysi ranglar/brend bo'limini boshqarmoqchisiz?:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_del_color_cat_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    page = int(data_parts[-1])
    brand = "_".join(data_parts[1:-1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, color_name, photo FROM colors WHERE brand = ?", (brand,))
    colors = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga (Brendlar)", callback_data="admin_del_colors_select_brand")]])

    if not colors:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Bu bo'limda ranglar mavjud emas.", reply_markup=back_kb)
        return
        
    total_pages = len(colors)
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0
        
    c_id, c_name, photo = colors[page]
    
    caption = f"🎨 <b>Rangni Boshqarish</b>\n🆔 <b>ID: {c_id}</b> | 📂 Brend: <b>{brand}</b>\n📄 Sahifa: {page+1} / {total_pages}"
    if c_name:
        caption += f"\nRang nomi/kodi: <b>{c_name}</b>"
        
    action_buttons = [
        [InlineKeyboardButton("❌ O'chirish", callback_data=f"adelcoldel_{brand}_{c_id}_{page}")]
    ]
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"adelcolcat_{brand}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"adelcolcat_{brand}_{page+1}"))
        
    if nav_buttons:
        action_buttons.append(nav_buttons)
        
    action_buttons.append([InlineKeyboardButton("⬅️ Orqaga (Brendlar)", callback_data="admin_del_colors_select_brand")])
    
    markup = InlineKeyboardMarkup(action_buttons)
    
    if photo:
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML", reply_markup=markup)

async def admin_del_color_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    data_parts = query.data.split("_")
    brand = data_parts[1]
    c_id = data_parts[2]
    current_page = int(data_parts[3])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM colors WHERE id = ?", (c_id,))
    conn.commit()
    conn.close()
    
    try:
        await query.message.delete()
        await query.answer("Rang o'chirildi!")
    except:
        await query.answer("Rang o'chirildi!")
    
    next_page = current_page - 1 if current_page > 0 else 0
    query.data = f"adelcolcat_{brand}_{next_page}"
    await admin_del_color_cat_view(update, context)

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
        states={ADD_NEW_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_brand_save)]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")]
    )
    application.add_handler(add_brand_handler)

    del_brand_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(del_brand_start, pattern="^abrand_del$")],
        states={DEL_BRAND: [CallbackQueryHandler(del_brand_execute, pattern="^delbrand_")]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")]
    )
    application.add_handler(del_brand_handler)

    # --- Video qo'shish Conversation Handler ---
    add_video_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_video_menu, pattern="^admin_add_video_menu$")],
        states={
            ADD_VIDEO_CAT: [
                CallbackQueryHandler(admin_add_video_cat_selected, pattern="^vcat_"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")
            ],
            ADD_VIDEO_FILE: [
                MessageHandler(filters.VIDEO | filters.PHOTO | filters.DOCUMENT, admin_add_video_file),
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
                CallbackGridHandler if 'CallbackGridHandler' in globals() else CallbackQueryHandler(add_color_start, pattern="^acolor_start$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_brands_menu, pattern="^admin_brands_menu$")]
    )
    application.add_handler(add_color_handler)

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
        CallbackQueryHandler(admin_del_prod_menu, pattern="^admin_del_prod_menu$"),
        CallbackQueryHandler(admin_del_cat_view, pattern="^adelcat_"),
        CallbackQueryHandler(admin_del_prod_execute, pattern="^adelprod_del_"),
        CallbackQueryHandler(admin_del_colors_select_brand, pattern="^adel_colors_select_brand$"),
        CallbackQueryHandler(admin_del_color_cat_view, pattern="^adelcolcat_"),
        CallbackQueryHandler(admin_del_color_execute, pattern="^adelcoldel_"),
        
        CallbackQueryHandler(user_catalog_menu, pattern="^main_catalog$"),
        CallbackQueryHandler(user_yotoqxona_submenu, pattern="^subcat_yotoqxona$"),
        CallbackQueryHandler(user_catalog_click, pattern="^ucat_"),
        CallbackQueryHandler(user_colors_menu, pattern="^main_colors$"),
        CallbackQueryHandler(user_akril_submenu, pattern="^subcat_akril$"),
        CallbackQueryHandler(user_color_click, pattern="^ucol_"),
        
        # Videolar bo'limi handlerlari
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
