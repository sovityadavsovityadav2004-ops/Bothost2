import os, json, time, asyncio, logging, urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from openai import AsyncOpenAI

# ---------- CONFIG ----------
TELEGRAM_TOKEN = ("8379341658:AAEQIqdOyz8w8BZ-6tdwYD3FnG_1hSuaJKY")
OPENAI_API_KEY = ("sk-9CQ2sB9UiQvD0aiYrxNjDMcIU6pGlIQY0DKnYw4si3fXp1zM")
ADMIN_ID = ("8821288505", "0")

DEVELOPER = "Sovit Yadav"
VERSION = "v2.0 Advanced"
DB_FILE = "users.json"
RATE_LIMIT = 8  # seconds

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ---------- DATABASE ----------
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"users": [], "banned": [], "stats": {"images": 0, "messages": 0}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

db = load_db()

def register_user(uid):
    if uid not in db["users"]:
        db["users"].append(uid)
        save_db(db)

def is_banned(uid):
    return uid in db["banned"]

# ---------- RATE LIMIT ----------
user_last = {}
def check_rate(uid):
    now = time.time()
    if now - user_last.get(uid, 0) < RATE_LIMIT:
        return False
    user_last[uid] = now
    return True

# ---------- TEXT ANIMATION ----------
FANCY = {
    "a":"ᴀ","b":"ʙ","c":"ᴄ","d":"ᴅ","e":"ᴇ","f":"ꜰ","g":"ɢ","h":"ʜ",
    "i":"ɪ","j":"ᴊ","k":"ᴋ","l":"ʟ","m":"ᴍ","n":"ɴ","o":"ᴏ","p":"ᴘ",
    "q":"ǫ","r":"ʀ","s":"ꜱ","t":"ᴛ","u":"ᴜ","v":"ᴠ","w":"ᴡ","x":"x",
    "y":"ʏ","z":"ᴢ"
}

def fancy_text(text):
    return "".join(FANCY.get(c.lower(), c) for c in text)

async def type_animation(update, text, delay=0.35):
    """Typing effect — ek-ek karke reveal karta hai"""
    msg = await update.message.reply_text("▌")
    current = ""
    for ch in text:
        current += ch
        try:
            await msg.edit_text(current + " ▌")
        except Exception:
            pass
        await asyncio.sleep(delay)
    await msg.edit_text(current)

async def fade_animation(update, text):
    frames = ["░", "▒", "▓", "█"]
    msg = await update.message.reply_text("Loading...")
    for f in frames:
        await msg.edit_text(f"{f} {f} {f}")
        await asyncio.sleep(0.25)
    await msg.edit_text(text)

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid):
        await update.message.reply_text("🚫 Aap ban ho chuke ho.")
        return
    register_user(uid)

    text = (
        f"🤖 *Advanced Bot {VERSION}*\n\n"
        f"👨‍💻 Developer: *{DEVELOPER}*\n\n"
        "📌 Commands:\n"
        "/image <prompt> — image banao\n"
        "/animate <text> — typing animation\n"
        "/fancy <text> — fancy font\n"
        "/fade <text> — fade animation\n"
        "/model — model choose\n"
        "/help — madad\n"
        "/id — apni ID\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_cmd(update, context):
    text = (
        "📖 *Help Menu*\n\n"
        "🎨 `/image cyberpunk city`\n"
        "✨ `/animate Hello {user}`\n"
        "🔤 `/fancy soviet yadav`\n"
        "💫 `/fade Loading complete`\n"
        "🧠 `/model` — model select\n\n"
        f"👨‍💻 *Developer:* {DEVELOPER}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def id_cmd(update, context):
    u = update.effective_user
    await update.message.reply_text(
        f"🆔 ID: `{u.id}`\n👤 Name: {u.full_name}\n🔗 @{u.username or 'none'}",
        parse_mode="Markdown"
    )

async def model_cmd(update, context):
    kb = [
        [InlineKeyboardButton("DALL·E 3", callback_data="model:dall-e-3")],
        [InlineKeyboardButton("DALL·E 2", callback_data="model:dall-e-2")],
        [InlineKeyboardButton("Free (Pollinations)", callback_data="model:free")],
    ]
    await update.message.reply_text("🎨 Model choose karo:", reply_markup=InlineKeyboardMarkup(kb))

async def model_button(update, context):
    q = update.callback_query
    await q.answer()
    model = q.data.split(":")[1]
    context.user_data["model"] = model
    await q.edit_message_text(f"✅ Model set: `{model}`", parse_mode="Markdown")

# ---------- IMAGE GENERATION ----------
async def generate_image(prompt, model):
    if model == "free" or client is None:
        enc = urllib.parse.quote(prompt)
        return f"https://image.pollinations.ai/prompt/{enc}?width=1024&height=1024&nologo=true"
    resp = await client.images.generate(model=model, prompt=prompt, size="1024x1024", n=1)
    return resp.data[0].url

async def image_cmd(update, context):
    uid = update.effective_user.id
    if is_banned(uid):
        await update.message.reply_text("🚫 Aap ban ho.")
        return
    if not check_rate(uid):
        await update.message.reply_text(f"⏳ {RATE_LIMIT}s wait karo.")
        return

    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text("Use: `/image apna prompt`", parse_mode="Markdown")
        return

    model = context.user_data.get("model", "free")
    msg = await update.message.reply_text(f"🖼️ Generating... ({model})")
    try:
        url = await generate_image(prompt, model)
        await update.message.reply_photo(
            photo=url,
            caption=f"🎨 {prompt}\n🧠 {model}\n👨‍💻 {DEVELOPER}"
        )
        db["stats"]["images"] += 1
        save_db(db)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

# ---------- TEXT ANIMATION COMMANDS ----------
async def animate_cmd(update, context):
    text = " ".join(context.args) or "Hello from Soviet Yadav!"
    await type_animation(update, text)

async def fancy_cmd(update, context):
    text = " ".join(context.args) or "soviet yadav"
    await update.message.reply_text(fancy_text(text))

async def fade_cmd(update, context):
    text = " ".join(context.args) or "✨ Done ✨"
    await fade_animation(update, text)

# ---------- ADMIN PANEL ----------
def is_admin(uid):
    return uid == ADMIN_ID

async def admin_cmd(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied.")
        return
    text = (
        f"👑 *Admin Panel — {DEVELOPER}*\n\n"
        "/stats — bot stats\n"
        "/broadcast <msg> — sabko bhejo\n"
        "/ban <id> — user ban\n"
        "/unban <id> — unban\n"
        "/users — total users\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def stats_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    text = (
        f"📊 *Bot Stats*\n\n"
        f"👥 Users: {len(db['users'])}\n"
        f"🚫 Banned: {len(db['banned'])}\n"
        f"🖼️ Images: {db['stats']['images']}\n"
        f"💬 Messages: {db['stats']['messages']}\n"
        f"⚙️ Version: {VERSION}\n"
        f"👨‍💻 Dev: {DEVELOPER}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def broadcast_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Use: /broadcast <message>")
        return
    sent, failed = 0, 0
    for uid in db["users"]:
        try:
            await context.bot.send_message(uid, f"📢 {msg}")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Sent: {sent}, ❌ Failed: {failed}")

async def ban_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    try:
        uid = int(context.args[0])
    except Exception:
        await update.message.reply_text("Use: /ban <user_id>")
        return
    if uid not in db["banned"]:
        db["banned"].append(uid)
        save_db(db)
    await update.message.reply_text(f"🚫 Banned: {uid}")

async def unban_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    try:
        uid = int(context.args[0])
    except Exception:
        await update.message.reply_text("Use: /unban <user_id>")
        return
    if uid in db["banned"]:
        db["banned"].remove(uid)
        save_db(db)
    await update.message.reply_text(f"✅ Unbanned: {uid}")

async def users_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(f"👥 Total users: {len(db['users'])}")

# ---------- ECHO ----------
async def echo(update, context):
    if is_banned(update.effective_user.id):
        return
    db["stats"]["messages"] += 1
    save_db(db)
    await update.message.reply_text(
        f"❓ Samajh nahi aaya.\n/help dekho.\n\n👨‍💻 {DEVELOPER}"
    )

# ---------- MAIN ----------
def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN set nahi hai!")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CallbackQueryHandler(model_button, pattern="^model:"))
    app.add_handler(CommandHandler("image", image_cmd))
    app.add_handler(CommandHandler("animate", animate_cmd))
    app.add_handler(CommandHandler("fancy", fancy_cmd))
    app.add_handler(CommandHandler("fade", fade_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print(f"🤖 Bot {VERSION} by {DEVELOPER} chal raha hai...")
    app.run_polling()

if __name__ == "__main__":
    main()
