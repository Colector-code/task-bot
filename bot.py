import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Зберігання даних (файл tasks.json) ───────────────────────────────────────
DATA_FILE = "tasks.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": [], "admins": [], "next_id": 1}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Допоміжні функції ────────────────────────────────────────────────────────
def is_admin(user_id: int, data: dict) -> bool:
    return user_id in data["admins"]

def progress_bar(done: int, total: int) -> str:
    if total == 0:
        return "Немає завдань"
    filled = int((done / total) * 10)
    bar = "▓" * filled + "░" * (10 - filled)
    pct = int((done / total) * 100)
    return f"{bar} {pct}%"

def tasks_text(data: dict) -> str:
    tasks = data["tasks"]
    if not tasks:
        return "📋 Завдань поки немає."
    
    done = sum(1 for t in tasks if t["done"])
    total = len(tasks)
    lines = [f"📋 *Завдання ({done}/{total} виконано)*", f"`{progress_bar(done, total)}`", ""]
    
    for t in tasks:
        status = "✅" if t["done"] else "🔄"
        assignee = f" — _{t['assignee']}_" if t.get("assignee") else ""
        lines.append(f"{status} *{t['id']}.* {t['title']}{assignee}")
    
    return "\n".join(lines)

# ─── Команди ──────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id

    # Перший запуск — зробити першого користувача адміном
    if not data["admins"]:
        data["admins"].append(user_id)
        save_data(data)
        await update.message.reply_text(
            "👋 Привіт! Ти перший — тебе призначено *адміністратором*.\n\n"
            "📌 *Команди:*\n"
            "/tasks — список завдань\n"
            "/add Назва завдання — додати завдання\n"
            "/assign 1 @username — призначити виконавця\n"
            "/done 1 — відмітити виконаним\n"
            "/delete 1 — видалити завдання\n"
            "/makeadmin @username — зробити адміном\n"
            "/removeadmin @username — забрати права адміна\n"
            "/help — всі команди",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "👋 Привіт! Я бот для управління завданнями.\n"
            "Напиши /tasks щоб побачити список завдань.",
        )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    admin_note = "👑 *Ти адмін* — маєш повний доступ.\n\n" if is_admin(uid, data) else ""
    
    text = (
        f"{admin_note}"
        "📌 *Всі команди:*\n\n"
        "*Для всіх:*\n"
        "/tasks — переглянути всі завдання\n"
        "/done 1 — відмітити завдання #1 виконаним\n\n"
        "*Тільки для адмінів:*\n"
        "/add Назва — додати завдання\n"
        "/assign 1 @username — призначити виконавця\n"
        "/delete 1 — видалити завдання #1\n"
        "/undone 1 — повернути завдання #1 в роботу\n"
        "/makeadmin @username — зробити адміном\n"
        "/removeadmin @username — забрати права адміна\n"
        "/admins — список адмінів\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def tasks_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    keyboard = []
    for t in data["tasks"]:
        if not t["done"]:
            keyboard.append([InlineKeyboardButton(
                f"✅ Виконати: {t['title'][:30]}",
                callback_data=f"done_{t['id']}"
            )])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(
        tasks_text(data),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def add_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_admin(uid, data):
        await update.message.reply_text("❌ Тільки адміни можуть додавати завдання.")
        return

    title = " ".join(ctx.args)
    if not title:
        await update.message.reply_text("⚠️ Вкажи назву: /add Назва завдання")
        return

    task = {"id": data["next_id"], "title": title, "done": False, "assignee": None}
    data["tasks"].append(task)
    data["next_id"] += 1
    save_data(data)
    await update.message.reply_text(f"✅ Завдання #{task['id']} додано: *{title}*", parse_mode="Markdown")

async def done_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not ctx.args:
        await update.message.reply_text("⚠️ Вкажи номер: /done 1")
        return

    try:
        task_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Номер має бути числом.")
        return

    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        await update.message.reply_text(f"❌ Завдання #{task_id} не знайдено.")
        return

    task["done"] = True
    save_data(data)

    done = sum(1 for t in data["tasks"] if t["done"])
    total = len(data["tasks"])
    await update.message.reply_text(
        f"✅ Завдання #{task_id} виконано!\n`{progress_bar(done, total)}` {done}/{total}",
        parse_mode="Markdown"
    )

async def undone_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_admin(uid, data):
        await update.message.reply_text("❌ Тільки адміни можуть повертати завдання.")
        return

    try:
        task_id = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Вкажи номер: /undone 1")
        return

    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        await update.message.reply_text(f"❌ Завдання #{task_id} не знайдено.")
        return

    task["done"] = False
    save_data(data)
    await update.message.reply_text(f"🔄 Завдання #{task_id} повернено в роботу.")

async def delete_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_admin(uid, data):
        await update.message.reply_text("❌ Тільки адміни можуть видаляти завдання.")
        return

    try:
        task_id = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Вкажи номер: /delete 1")
        return

    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    if len(data["tasks"]) == before:
        await update.message.reply_text(f"❌ Завдання #{task_id} не знайдено.")
        return

    save_data(data)
    await update.message.reply_text(f"🗑️ Завдання #{task_id} видалено.")

async def assign_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_admin(uid, data):
        await update.message.reply_text("❌ Тільки адміни можуть призначати виконавців.")
        return

    if len(ctx.args) < 2:
        await update.message.reply_text("⚠️ Використання: /assign 1 @username")
        return

    try:
        task_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Номер має бути числом.")
        return

    assignee = ctx.args[1]
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        await update.message.reply_text(f"❌ Завдання #{task_id} не знайдено.")
        return

    task["assignee"] = assignee
    save_data(data)
    await update.message.reply_text(f"👤 Завдання #{task_id} призначено: {assignee}")

async def make_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_admin(uid, data):
        await update.message.reply_text("❌ Тільки адміни можуть призначати адмінів.")
        return

    if not ctx.args:
        await update.message.reply_text("⚠️ Вкажи: /makeadmin @username або ID")
        return

    # Підтримка як @username так і числового ID
    target = ctx.args[0].lstrip("@")
    await update.message.reply_text(
        f"⚠️ Щоб призначити адміна, потрібен його Telegram ID.\n"
        f"Попроси {target} написати /myid в чаті, щоб дізнатись свій ID."
    )

async def my_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    await update.message.reply_text(f"🪪 *{name}*, твій Telegram ID: `{uid}`", parse_mode="Markdown")

async def add_admin_by_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_admin(uid, data):
        await update.message.reply_text("❌ Тільки адміни можуть призначати адмінів.")
        return

    try:
        target_id = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Використання: /addadmin 123456789")
        return

    if target_id in data["admins"]:
        await update.message.reply_text("⚠️ Цей користувач вже є адміном.")
        return

    data["admins"].append(target_id)
    save_data(data)
    await update.message.reply_text(f"👑 Користувач {target_id} тепер адмін.")

async def remove_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_admin(uid, data):
        await update.message.reply_text("❌ Тільки адміни можуть забирати права.")
        return

    try:
        target_id = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Використання: /removeadmin 123456789")
        return

    if target_id not in data["admins"]:
        await update.message.reply_text("⚠️ Цей користувач не є адміном.")
        return

    if target_id == uid:
        await update.message.reply_text("❌ Не можна зняти права з себе.")
        return

    data["admins"].remove(target_id)
    save_data(data)
    await update.message.reply_text(f"✅ Права адміна знято з користувача {target_id}.")

async def list_admins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["admins"]:
        await update.message.reply_text("Адмінів немає.")
        return
    ids = "\n".join(f"• `{a}`" for a in data["admins"])
    await update.message.reply_text(f"👑 *Адміни:*\n{ids}", parse_mode="Markdown")

# ─── Callback кнопки ──────────────────────────────────────────────────────────
async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()

    if query.data.startswith("done_"):
        task_id = int(query.data.split("_")[1])
        task = next((t for t in data["tasks"] if t["id"] == task_id), None)
        if task and not task["done"]:
            task["done"] = True
            save_data(data)
            done = sum(1 for t in data["tasks"] if t["done"])
            total = len(data["tasks"])
            await query.edit_message_text(
                tasks_text(data) + f"\n\n✅ Завдання #{task_id} виконано!\n`{progress_bar(done, total)}`",
                parse_mode="Markdown"
            )

# ─── Запуск ───────────────────────────────────────────────────────────────────
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("❌ Не знайдено BOT_TOKEN у змінних середовища!")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("done", done_task))
    app.add_handler(CommandHandler("undone", undone_task))
    app.add_handler(CommandHandler("delete", delete_task))
    app.add_handler(CommandHandler("assign", assign_task))
    app.add_handler(CommandHandler("makeadmin", make_admin))
    app.add_handler(CommandHandler("addadmin", add_admin_by_id))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("admins", list_admins))
    app.add_handler(CommandHandler("myid", my_id))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("🤖 Бот запущено!")
    app.run_polling()

if __name__ == "__main__":
    main()
