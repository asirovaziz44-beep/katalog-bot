from flask import Flask
from threading import Thread

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

(
    ADD_CAT, ADD_PHOTO, ADD_DESC, 
    ADD_BRAND_MENU, ADD_NEW_BRAND, ADD_COLOR_PHOTO, ADD_COLOR_NAME,
    SET_LOGO, SET_INFO, SET_WELCOME, DEL_BRAND
) = range(11)

def init_db():
    conn = sqlite3.connect("furniture_bot.db")
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
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_colors_brand ON colors(brand)")
    
    default_brands = ["Stoleshnitsa", "Akril (Umumiy)", "Akril: Kashtan", "Akril: Kastaman", "MDF / LDSP", "Yeger Premium"]
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
            [InlineKeyboardButton("📞 Контакты", callback_data="main_info"),
             InlineKeyboardButton("🌐 Язык", callback_data="main_lang")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📁 Katalog", callback_data="main_catalog"),
             InlineKeyboardButton("🎨 Ranglar / Brendlar", callback_data="main_colors")],
            [InlineKeyboardButton("📞 Aloqa", callback_data="main_info"),
             InlineKeyboardButton("🌐 Til", callback_data="main_lang")]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_current_lang():
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'language'")
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "uz"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_current_lang()
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'welcome_text'")
    res_text = cursor.fetchone()
    
    if lang == "ru":
        default_t = "Здравствуйте, {user_name}!\nДобро пожаловать в каталог современной мебели."
    else:
        default_t = "Assalomu alaykum, {user_name}!\nZamonaviy mebellar katalogiga xush kelibsiz."
        
    template = res_text[0] if res_text else default_t
    text = template.replace("{user_name}", user.first_name)
    
    cursor.execute("SELECT value FROM settings WHERE key = 'logo'")
    res_logo = cursor.fetchone()
    logo_file_id = res_logo[0] if res_logo else None
    conn.close()

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

# --- USER: KATALOG ---
async def user_catalog_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("🛏 Спальня", callback_data="subcat_yotoqxona")],
            [InlineKeyboardButton("🍳 Кухня", callback_data="ucat_Oshxona"),
             InlineKeyboardButton("🛋 Мягкая мебель", callback_data="ucat_Yumshoq_mebel")],
            [InlineKeyboardButton("🚪 Прихожая", callback_data="ucat_Koridor"),
             InlineKeyboardButton("📺 ТВ зона", callback_data="ucat_TV_zona")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        caption_text = "Выберите категорию:"
    else:
        keyboard = [
            [InlineKeyboardButton("🛏 Yotoqxona", callback_data="subcat_yotoqxona")],
            [InlineKeyboardButton("🍳 Oshxona", callback_data="ucat_Oshxona"),
             InlineKeyboardButton("🛋 Yumshoq mebel", callback_data="ucat_Yumshoq_mebel")],
            [InlineKeyboardButton("🚪 Koridor", callback_data="ucat_Koridor"),
             InlineKeyboardButton("📺 TV zona", callback_data="ucat_TV_zona")],
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
            [InlineKeyboardButton("🛏 Спальня для взрослых", callback_data="ucat_Kattalar_yotoqxonasi")],
            [InlineKeyboardButton("🧸 Детская спальня", callback_data="ucat_Bolalar_yotoqxonasi")],
            [InlineKeyboardButton("🚪 Шкаф-купе / Гардероб", callback_data="ucat_Shkaf_kupe_garderob")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main_catalog")]
        ]
        caption_text = "Выберите раздел спальни:"
    else:
        keyboard = [
            [InlineKeyboardButton("🛏 Kattalar yotoqxonasi", callback_data="ucat_Kattalar_yotoqxonasi")],
            [InlineKeyboardButton("🧸 Bolalar yotoqxonasi", callback_data="ucat_Bolalar_yotoqxonasi")],
            [InlineKeyboardButton("🚪 Shkaf kupe / Garderob", callback_data="ucat_Shkaf_kupe_garderob")],
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
    cat = data_parts[1]
    page = int(data_parts[2]) if len(data_parts) > 2 else 0
    
    lang = get_current_lang()
    back_text = "Назад" if lang == "ru" else "Orqaga"
    order_text = "🛒 Buyurtma berish" if lang != "ru" else "🛒 Заказать"
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, description, photo FROM products WHERE category = ?", (cat,))
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
    start_idx = page * limit
    end_idx = start_idx + limit
    page_products = products[start_idx:end_idx]
    
    order_btn = InlineKeyboardButton(order_text, url=f"https://t.me/{MANAGER_USERNAME}")
    
    for p in page_products:
        title, desc, photo = p[0], p[1], p[2]
        caption = f"<b>{title}</b>"
        if desc:
            caption += f"\n\n{desc}"
            
        item_kb = InlineKeyboardMarkup([[order_btn]])
        
        if photo:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=item_kb)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML", disable_web_page_preview=True, reply_markup=item_kb)
            
    total_pages = (len(products) + limit - 1) // limit
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"• {i+1} •" if i == page else str(i+1)
        page_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"ucat_{cat}_{i}"))
        
    keyboard_layout = []
    if len(page_buttons) > 1:
        keyboard_layout.append(page_buttons)
        
    keyboard_layout.append([InlineKeyboardButton(f"⬅️ {back_text}", callback_data=back_callback)])
    
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text="Sahifani tanlang:" if lang != "ru" else "Выберите страницу:", 
        reply_markup=InlineKeyboardMarkup(keyboard_layout)
    )

# --- USER: RANGLAR / BRENDLAR ---
async def user_colors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("🪵 Столешница", callback_data="ucol_Stoleshnitsa_0")],
            [InlineKeyboardButton("✨ Акрил", callback_data="subcat_akril")],
            [InlineKeyboardButton("🚪 MDF / LDSP", callback_data="ucol_MDF_LDSP_0")],
            [InlineKeyboardButton("⭐ Yeger Premium", callback_data="ucol_Yeger_Premium_0")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        cap = "Выберите материал или бренд:"
    else:
        keyboard = [
            [InlineKeyboardButton("🪵 Stoleshnitsa", callback_data="ucol_Stoleshnitsa_0")],
            [InlineKeyboardButton("✨ Akril", callback_data="subcat_akril")],
            [InlineKeyboardButton("🚪 MDF / LDSP", callback_data="ucol_MDF_LDSP_0")],
            [InlineKeyboardButton("⭐ Yeger premium", callback_data="ucol_Yeger_Premium_0")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")]
        ]
        cap = "Kerakli material yoki brendni tanlang:"
    
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=cap, reply_markup=InlineKeyboardMarkup(keyboard))

async def user_akril_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    if lang == "ru":
        keyboard = [
            [InlineKeyboardButton("✨ Акрил (Общий)", callback_data="ucol_Akril_Umumiy_0")],
            [InlineKeyboardButton("🔷 Акрил: Каштан", callback_data="ucol_Akril_Kashtan_0"),
             InlineKeyboardButton("🔶 Акрил: Кастаман", callback_data="ucol_Akril_Kastaman_0")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main_colors")]
        ]
        cap = "Выберите раздел акрила:"
    else:
        keyboard = [
            [InlineKeyboardButton("✨ Akril (Umumiy)", callback_data="ucol_Akril_Umumiy_0")],
            [InlineKeyboardButton("🔷 Akril: Kashtan", callback_data="ucol_Akril_Kashtan_0"),
             InlineKeyboardButton("🔶 Akril: Kastaman", callback_data="ucol_Akril_Kastaman_0")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_colors")]
        ]
        cap = "Akril bo'limini tanlang:"
        
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
    brand_parts = data_parts[1:-1]
    brand_clean_query = "_".join(brand_parts)
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM brands")
    brands = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    selected_brand = None
    for b in brands:
        clean_b = b.replace(' ', '_').replace('/', '').replace(':', '')
        if clean_b == brand_clean_query:
            selected_brand = b
            break
            
    try:
        await query.message.delete()
    except:
        pass

    if not selected_brand:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik.", reply_markup=main_menu_keyboard(lang))
        return

    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT color_name, photo FROM colors WHERE brand = ?", (selected_brand,))
    colors = cursor.fetchall()
    conn.close()
    
    if "Akril" in selected_brand:
        back_callback = "subcat_akril"
    else:
        back_callback = "main_colors"

    back_text_str = "Назад" if lang == "ru" else "Orqaga"
    order_text = "🛒 Buyurtma berish" if lang != "ru" else "🛒 Заказать"
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(back_text_str, callback_data=back_callback)]])
    
    if not colors:
        msg = f"Для раздела '{selected_brand}' цвета еще не добавлены." if lang == "ru" else f"'{selected_brand}' bo'limi uchun ranglar hali kiritilmagan."
        await context.bot.send_message(chat_id=query.message.chat_id, text=msg, reply_markup=back_kb)
        return
        
    limit = 5
    start_idx = page * limit
    end_idx = start_idx + limit
    page_colors = colors[start_idx:end_idx]
    
    order_btn = InlineKeyboardButton(order_text, url=f"https://t.me/{MANAGER_USERNAME}")

    for c in page_colors:
        c_name, photo = c[0], c[1]
        caption = f"🎨 Раздел: <b>{selected_brand}</b>" if lang == "ru" else f"🎨 Bo'lim: <b>{selected_brand}</b>"
        if c_name:
            caption += f"\nКод/Название: <b>{c_name}</b>" if lang == "ru" else f"\nRang nomi/kodi: <b>{c_name}</b>"
            
        item_kb = InlineKeyboardMarkup([[order_btn]])
        
        if photo:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=item_kb)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=caption, parse_mode="HTML", reply_markup=item_kb)
            
    total_pages = (len(colors) + limit - 1) // limit
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"• {i+1} •" if i == page else str(i+1)
        page_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"ucol_{brand_clean_query}_{i}"))
        
    keyboard_layout = []
    if len(page_buttons) > 1:
        keyboard_layout.append(page_buttons)
        
    keyboard_layout.append([InlineKeyboardButton(back_text_str, callback_data=back_callback)])
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="Sahifani tanlang:" if lang != "ru" else "Выберите страницу:", reply_markup=InlineKeyboardMarkup(keyboard_layout))

# --- ALOQA VA TIL ---
async def main_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_current_lang()
    
    conn = sqlite3.connect("furniture_bot.db")
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
    
    conn = sqlite3.connect("furniture_bot.db")
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

# --- ADMIN PANEL ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🖼 Logotipni o'zgartirish", callback_data="admin_logo"),
         InlineKeyboardButton("💬 Salomlashish matni", callback_data="admin_welcome")],
        [InlineKeyboardButton("⚙️ Ma'lumotlarni sozlash", callback_data="admin_settings"),
         InlineKeyboardButton("🎨 Brendlar va Ranglar", callback_data="admin_brands_menu")],
        [InlineKeyboardButton("➕ Yangi Mahsulot Qo'shish", callback_data="admin_add_prod"),
         InlineKeyboardButton("🗑 Rasmlarni O'chirish", callback_data="admin_del_prod")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
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

async def admin_welcome_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect("furniture_bot.db")
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
    conn = sqlite3.connect("furniture_bot.db")
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
    text = "➕ Yangi brend yoki bo'lim nomini yuboring\n(masalan: <i>Akril: Yeni</i> yoki <i>MDF Matte</i>):"
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_kb, parse_mode="HTML")
    return ADD_NEW_BRAND

async def add_brand_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    brand_name = update.message.text.strip()
    conn = sqlite3.connect("furniture_bot.db")
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
    conn = sqlite3.connect("furniture_bot.db")
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
    
    conn = sqlite3.connect("furniture_bot.db")
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
    
    conn = sqlite3.connect("furniture_bot.db")
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
    
    conn = sqlite3.connect("furniture_bot.db")
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
    text = f"Tanlandi: {brand_name}\n\n📸 Endi material / rang namunasining rasmini yuboring (yoki Orqaga tugmasini bosing):"
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
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO colors (brand, color_name, photo) VALUES (?, ?, ?)", (brand, c_name, photo))
    conn.commit()
    conn.close()
    
    lang = get_current_lang()
    await update.message.reply_text("✅ Rang/material muvaffaqiyatli qo'shildi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

async def add_color_name_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    brand = context.user_data['color_brand']
    photo = context.user_data['color_photo']
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO colors (brand, color_name, photo) VALUES (?, ?, ?)", (brand, "", photo))
    conn.commit()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
    lang = get_current_lang()
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Rang/material muvaffaqiyatli qo'shildi!\nAsosiy menyu:", reply_markup=main_menu_keyboard(lang))
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
    conn = sqlite3.connect("furniture_bot.db")
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
    conn = sqlite3.connect("furniture_bot.db")
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
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    p_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM colors")
    c_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM brands")
    b_count = cursor.fetchone()[0]
    conn.close()
    
    text = f"📊 <b>Statistika</b>\n\n- Jami mahsulotlar: {p_count} ta\n- Jami ranglar/materiallar: {c_count} ta\n- Jami brend/bo'limlar: {b_count} ta"
    reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")]])
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode="HTML", reply_markup=reply_kb)

# --- ADD PRODUCT CONVERSATION ---
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
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_add_prod")]
    ]
    try:
        await query.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="Yotoqxona turini tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_CAT

async def add_prod_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
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
        [InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="skip_desc")],
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
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (category, title, description, photo) VALUES (?, ?, ?, ?)",
                   (cat, "Mahsulot", desc, photo))
    conn.commit()
    conn.close()
    
    lang = get_current_lang()
    await update.message.reply_text("✅ Mahsulot muvaffaqiyatli qo'shildi!", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

async def add_prod_desc_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = context.user_data.get('prod_cat', 'Boshqa')
    photo = context.user_data.get('prod_photo')
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (category, title, description, photo) VALUES (?, ?, ?, ?)",
                   (cat, "Mahsulot", "", photo))
    conn.commit()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
    lang = get_current_lang()
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Mahsulot muvaffaqiyatli qo'shildi!\nAsosiy menyu:", reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END

# --- RASMLARni ID VA SAHIFA BILAN KO'RIB CHIQIB O'CHIRISH ---
async def del_prod_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    if len(data_parts) > 1 and data_parts[1].isdigit():
        page = int(data_parts[1])
    elif context.args and context.args[0].isdigit():
        page = int(context.args[0])
    else:
        page = 0
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, description, photo FROM products")
    items = cursor.fetchall()
    conn.close()
    
    try:
        await query.message.delete()
    except:
        pass
        
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga (Admin panel)", callback_data="back_to_admin")]])

    if not items:
        await context.bot.send_message(chat_id=query.message.chat_id, text="O'chirish uchun mahsulotlar qolmagan.", reply_markup=back_kb)
        return
        
    if page >= len(items):
        page = len(items) - 1
    if page < 0:
        page = 0
        
    prod_id, cat, desc, photo = items[page]
    
    caption = f"🗑 <b>Mahsulotni O'chirish</b>\n🆔 <b>ID raqami: {prod_id}</b>\n📂 Bo'lim: <b>{cat}</b>"
    if desc:
        caption += f"\n\n{desc}"
        
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"delview_{page-1}"))
        
    nav_buttons.append(InlineKeyboardButton(f"❌ O'chirish (ID: {prod_id})", callback_data=f"deldone_{prod_id}_{page}"))
    
    if page < len(items) - 1:
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"delview_{page+1}"))
        
    keyboard_layout = [
        nav_buttons,
        [InlineKeyboardButton("⬅️ Orqaga (Admin panel)", callback_data="back_to_admin")]
    ]
    
    if photo:
        await context.bot.send_photo(
            chat_id=query.message.chat_id, 
            photo=photo, 
            caption=caption, 
            parse_mode="HTML", 
            reply_markup=InlineKeyboardMarkup(keyboard_layout)
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id, 
            text=caption, 
            parse_mode="HTML", 
            reply_markup=InlineKeyboardMarkup(keyboard_layout)
        )

async def del_prod_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    prod_id = data_parts[1]
    current_page = int(data_parts[2])
    
    conn = sqlite3.connect("furniture_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    
    next_page = current_page if current_page > 0 else 0
    
    context.args = [str(next_page)]
    await del_prod_view(update, context)

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

    add_color_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_color_start, pattern="^acolor_start$")],
        states={
            ADD_BRAND_MENU: [CallbackQueryHandler(add_color_brand, pattern="^abrand_")],
            ADD_COLOR_PHOTO: [
                MessageHandler(filters.PHOTO, add_color_photo),
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

    add_product_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_prod, pattern="^admin_add_prod$")],
        states={
            ADD_CAT: [
                CallbackQueryHandler(admin_add_prod_yotoqxona, pattern="^acat_yotoqxona_menu$"),
                CallbackQueryHandler(add_prod_cat, pattern="^cat_"),
                CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$"),
                CallbackQueryHandler(admin_add_prod, pattern="^admin_add_prod$")
            ],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, add_prod_photo),
                CallbackQueryHandler(admin_add_prod, pattern="^admin_add_prod$")
            ],
            ADD_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_prod_desc_text),
                CallbackQueryHandler(add_prod_desc_skip, pattern="^skip_desc$"),
                CallbackQueryHandler(admin_add_prod, pattern="^admin_add_prod$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$")]
    )
    application.add_handler(add_product_handler)

    application.add_handler(CallbackQueryHandler(del_prod_view, pattern="^admin_del_prod$|^delview_"))
    application.add_handler(CallbackQueryHandler(del_prod_execute, pattern="^deldone_"))

    application.add_handlers([
        CallbackQueryHandler(user_catalog_menu, pattern="^main_catalog$"),
        CallbackQueryHandler(user_yotoqxona_submenu, pattern="^subcat_yotoqxona$"),
        CallbackQueryHandler(user_catalog_click, pattern="^ucat_"),
        CallbackQueryHandler(user_colors_menu, pattern="^main_colors$"),
        CallbackQueryHandler(user_akril_submenu, pattern="^subcat_akril$"),
        CallbackQueryHandler(user_color_click, pattern="^ucol_"),
        CallbackQueryHandler(main_info, pattern="^main_info$"),
        CallbackQueryHandler(main_lang, pattern="^main_lang$"),
        CallbackQueryHandler(set_lang, pattern="^set_lang_"),
        CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
    ])
    keep_alive()
    print("Bot muvaffaqiyatli ishga tushdi...")
    application.run_polling()
