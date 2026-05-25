import html
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    BOT_NAME,
    PANEL_NAME,
    HOST,
    SSH_PORT,
    WS_PORT,
    SSL_PORT,
    UDP_CUSTOM,
)

DB = "darkzsaid.db"


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        name TEXT PRIMARY KEY,
        value INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vip_users (
        telegram_id INTEGER PRIMARY KEY
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        ssh_user TEXT UNIQUE,
        ssh_pass TEXT,
        plan TEXT,
        expire_date TEXT,
        max_connections INTEGER
    )
    """)

    defaults = {
        "free_days": 3,
        "free_connections": 1,
        "free_max_accounts": 1,
        "vip_days": 30,
        "vip_connections": 3,
        "vip_max_accounts": 5,
    }

    for key, value in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (key, value))

    con.commit()
    con.close()


def update_db_columns():
    con = db()
    cur = con.cursor()

    try:
        cur.execute("ALTER TABLE accounts ADD COLUMN ssh_pass TEXT")
    except sqlite3.OperationalError:
        pass

    con.commit()
    con.close()


def get_setting(name):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT value FROM settings WHERE name=?", (name,))
    row = cur.fetchone()
    con.close()
    return row[0]


def set_setting(name, value):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE settings SET value=? WHERE name=?", (value, name))
    con.commit()
    con.close()


def is_vip(telegram_id):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT telegram_id FROM vip_users WHERE telegram_id=?", (telegram_id,))
    row = cur.fetchone()
    con.close()
    return row is not None


def add_vip(telegram_id):
    con = db()
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO vip_users VALUES (?)", (telegram_id,))
    con.commit()
    con.close()


def remove_vip(telegram_id):
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM vip_users WHERE telegram_id=?", (telegram_id,))
    con.commit()
    con.close()


def count_accounts(telegram_id, plan):
    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM accounts WHERE telegram_id=? AND plan=?",
        (telegram_id, plan),
    )
    total = cur.fetchone()[0]
    con.close()
    return total


def save_account(telegram_id, ssh_user, ssh_pass, plan, expire_date, max_connections):
    con = db()
    cur = con.cursor()
    cur.execute("""
    INSERT INTO accounts 
    (telegram_id, ssh_user, ssh_pass, plan, expire_date, max_connections)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (telegram_id, ssh_user, ssh_pass, plan, expire_date, max_connections))
    con.commit()
    con.close()


def list_accounts():
    con = db()
    cur = con.cursor()
    cur.execute("""
    SELECT telegram_id, ssh_user, ssh_pass, plan, expire_date, max_connections 
    FROM accounts
    ORDER BY id DESC
    """)
    rows = cur.fetchall()
    con.close()
    return rows


def list_my_accounts(telegram_id):
    con = db()
    cur = con.cursor()
    cur.execute("""
    SELECT ssh_user, ssh_pass, plan, expire_date, max_connections
    FROM accounts
    WHERE telegram_id=?
    ORDER BY id DESC
    """, (telegram_id,))
    rows = cur.fetchall()
    con.close()
    return rows


def delete_account_db(ssh_user):
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM accounts WHERE ssh_user=?", (ssh_user,))
    con.commit()
    con.close()


def list_vip_users():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT telegram_id FROM vip_users")
    rows = cur.fetchall()
    con.close()
    return rows


def valid_username(username):
    return re.match(r"^[a-zA-Z0-9_]{3,16}$", username)


def valid_password(password):
    return len(password) >= 4 and " " not in password


def linux_user_exists(username):
    result = subprocess.run(
        ["id", username],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def create_linux_user(username, password, expire_date, max_connections):
    subprocess.run(["useradd", "-M", "-s", "/bin/false", username], check=True)

    subprocess.run(
        ["chpasswd"],
        input=f"{username}:{password}".encode(),
        check=True,
    )

    subprocess.run(["chage", "-E", expire_date, username], check=True)

    limits_file = "/etc/security/limits.d/darkzsaid-ssh.conf"
    line = f"{username} hard maxlogins {max_connections}\n"

    with open(limits_file, "a") as f:
        f.write(line)


def delete_linux_user(username):
    subprocess.run(
        ["pkill", "-u", username],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        ["userdel", "-f", username],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def clean_expired_accounts():
    today = datetime.now().strftime("%Y-%m-%d")

    con = db()
    cur = con.cursor()

    cur.execute("SELECT ssh_user FROM accounts WHERE expire_date < ?", (today,))
    rows = cur.fetchall()

    for row in rows:
        ssh_user = row[0]
        delete_linux_user(ssh_user)
        cur.execute("DELETE FROM accounts WHERE ssh_user=?", (ssh_user,))

    con.commit()
    con.close()


def server_info():
    uptime = subprocess.getoutput("uptime -p")
    ram = subprocess.getoutput("free -h | grep Mem")
    disk = subprocess.getoutput("df -h / | tail -1")
    users = subprocess.getoutput("who | wc -l")

    return f"""
📡 Info servidor

🖥 Host: {HOST}
⏱ Uptime: {uptime}

💾 RAM:
{ram}

📀 Disco:
{disk}

👥 Sesiones activas: {users}
"""


def main_menu(user_id):
    keyboard = [
        [InlineKeyboardButton("👤 Crear SSH", callback_data="create_ssh")],
        [
            InlineKeyboardButton("📋 Mis cuentas", callback_data="active_accounts"),
            InlineKeyboardButton("💳 Mi cuenta", callback_data="my_account"),
        ],
        [InlineKeyboardButton("📡 Info servidor", callback_data="server_info")],
        [InlineKeyboardButton("🔥 Panel DarkZsaid", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Volver al menú", callback_data="back")]
    ])


def back_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_panel")],
        [InlineKeyboardButton("🏠 Menú principal", callback_data="back")],
    ])


def admin_menu():
    keyboard = [
        [
            InlineKeyboardButton("🆓 Configurar FREE", callback_data="config_free"),
            InlineKeyboardButton("💎 Configurar VIP", callback_data="config_vip"),
        ],
        [
            InlineKeyboardButton("➕ Dar VIP", callback_data="add_vip"),
            InlineKeyboardButton("❌ Quitar VIP", callback_data="remove_vip"),
        ],
        [
            InlineKeyboardButton("👥 Ver VIP", callback_data="list_vip"),
            InlineKeyboardButton("📋 Ver cuentas", callback_data="list_accounts"),
        ],
        [
            InlineKeyboardButton("🗑 Eliminar SSH", callback_data="delete_ssh"),
            InlineKeyboardButton("📡 Info servidor", callback_data="server_info"),
        ],
        [InlineKeyboardButton("🏠 Menú principal", callback_data="back")],
    ]

    return InlineKeyboardMarkup(keyboard)


def free_config_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Cambiar días FREE", callback_data="set_free_days")],
        [InlineKeyboardButton("🔌 Cambiar conexiones FREE", callback_data="set_free_connections")],
        [InlineKeyboardButton("👤 Cambiar máximo cuentas FREE", callback_data="set_free_max_accounts")],
        [InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def vip_config_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Cambiar días VIP", callback_data="set_vip_days")],
        [InlineKeyboardButton("🔌 Cambiar conexiones VIP", callback_data="set_vip_connections")],
        [InlineKeyboardButton("👤 Cambiar máximo cuentas VIP", callback_data="set_vip_max_accounts")],
        [InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_expired_accounts()
    context.user_data.clear()
    user_id = update.effective_user.id

    tg_name = update.effective_user.first_name or "Usuario"
    tg_username = update.effective_user.username or "sin_usuario"

    text = f"""
━━━━━━━━━━━━━━━━━━━━
     ⚡ DARKZSAID SSH BOT ⚡
  Panel automático de cuentas SSH
       Creado por @DarkZsaid
━━━━━━━━━━━━━━━━━━━━

👤 Nombre: {tg_name}
🆔 Usuario: @{tg_username}
💳 Créditos: 1/1 🟢

🌐 Elige acción:
📅 Cuentas válidas por 3 días
"""

    await update.message.reply_text(text, reply_markup=main_menu(user_id))


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_expired_accounts()

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "back":
        context.user_data.clear()
        tg_name = query.from_user.first_name or "Usuario"
        tg_username = query.from_user.username or "sin_usuario"

        await query.edit_message_text(
            f"""
━━━━━━━━━━━━━━━━━━━━
     ⚡ DARKZSAID SSH BOT ⚡
  Panel automático de cuentas SSH
       Creado por @DarkZsaid
━━━━━━━━━━━━━━━━━━━━

👤 Nombre: {tg_name}
🆔 Usuario: @{tg_username}
💳 Créditos: 1/1 🟢

🌐 Elige acción:
📅 Cuentas válidas por 3 días
""",
            reply_markup=main_menu(user_id),
        )

    elif data == "create_ssh":
        context.user_data.clear()
        context.user_data["step"] = "ask_username"

        await query.edit_message_text(
            "👤 Escribe el nombre de usuario SSH que quieres.\n\n"
            "Ejemplo: juan123\n\n"
            "Reglas:\n"
            "- mínimo 3 caracteres\n"
            "- máximo 16 caracteres\n"
            "- sin espacios\n"
            "- solo letras, números y _",
            reply_markup=back_menu(),
        )

    elif data == "my_account":
        plan = "VIP" if is_vip(user_id) else "FREE"

        if plan == "VIP":
            days = get_setting("vip_days")
            connections = get_setting("vip_connections")
            max_accounts = get_setting("vip_max_accounts")
        else:
            days = get_setting("free_days")
            connections = get_setting("free_connections")
            max_accounts = get_setting("free_max_accounts")

        await query.edit_message_text(
            f"""
ℹ️ Mi cuenta

📦 Plan: {plan}
📅 Duración: {days} días
🔌 Conexiones: {connections}
👤 Máximo cuentas activas: {max_accounts}
""",
            reply_markup=back_menu(),
        )

    elif data == "my_accounts":
        rows = list_my_accounts(user_id)

        if not rows:
            await query.edit_message_text(
                "📋 No tienes cuentas SSH activas.",
                reply_markup=back_menu(),
            )
            return

        text = "📋 Tus cuentas activas:\n\n"

        for row in rows:
            ssh_user, ssh_pass, plan, expire_date, max_connections = row

            if not ssh_pass:
                ssh_pass = "No guardada"

            text += f"""
✅ Cuenta SSH

👤 Usuario: {ssh_user}
🔑 Password: {ssh_pass}

📅 Expira: {expire_date}
🔌 Conexiones: {max_connections}
📦 Plan: {plan}

🌐 Host: {HOST}
🚪 SSH: {SSH_PORT}
🌍 WebSocket: {WS_PORT}
🔐 SSL/TLS: {SSL_PORT}
🎮 UDP CUSTOM: {UDP_CUSTOM}

━━━━━━━━━━━━━━
"""

        await query.edit_message_text(
            text[:3900],
            reply_markup=back_menu(),
        )

    elif data == "server_info":
        info = server_info()

        if user_id == ADMIN_ID:
            await query.edit_message_text(info, reply_markup=back_admin_menu())
        else:
            await query.edit_message_text(info, reply_markup=back_menu())

    elif data == "admin_panel":
        context.user_data.clear()

        if user_id != ADMIN_ID:
            await query.edit_message_text(
                "❌ No tienes permiso.",
                reply_markup=back_menu(),
            )
            return

        await query.edit_message_text(
            f"👑 {PANEL_NAME}",
            reply_markup=admin_menu(),
        )

    elif data == "config_free":
        if user_id != ADMIN_ID:
            return

        text = f"""
🆓 Configuración FREE

📅 Días: {get_setting("free_days")}
🔌 Conexiones: {get_setting("free_connections")}
👤 Máximo cuentas: {get_setting("free_max_accounts")}
"""
        await query.edit_message_text(text, reply_markup=free_config_menu())

    elif data == "config_vip":
        if user_id != ADMIN_ID:
            return

        text = f"""
💎 Configuración VIP

📅 Días: {get_setting("vip_days")}
🔌 Conexiones: {get_setting("vip_connections")}
👤 Máximo cuentas: {get_setting("vip_max_accounts")}
"""
        await query.edit_message_text(text, reply_markup=vip_config_menu())

    elif data.startswith("set_"):
        if user_id != ADMIN_ID:
            return

        context.user_data.clear()
        context.user_data["step"] = data

        await query.edit_message_text(
            "✍️ Escribe el nuevo número:",
            reply_markup=back_admin_menu(),
        )

    elif data == "add_vip":
        if user_id != ADMIN_ID:
            return

        context.user_data.clear()
        context.user_data["step"] = "add_vip"

        await query.edit_message_text(
            "➕ Escribe el ID de Telegram para darle VIP:",
            reply_markup=back_admin_menu(),
        )

    elif data == "remove_vip":
        if user_id != ADMIN_ID:
            return

        context.user_data.clear()
        context.user_data["step"] = "remove_vip"

        await query.edit_message_text(
            "❌ Escribe el ID de Telegram para quitar VIP:",
            reply_markup=back_admin_menu(),
        )

    elif data == "list_vip":
        if user_id != ADMIN_ID:
            return

        rows = list_vip_users()

        if not rows:
            await query.edit_message_text(
                "👥 No hay usuarios VIP.",
                reply_markup=back_admin_menu(),
            )
            return

        text = "👥 Usuarios VIP:\n\n"
        for row in rows:
            text += f"💎 {row[0]}\n"

        await query.edit_message_text(
            text,
            reply_markup=back_admin_menu(),
        )

    elif data == "list_accounts":
        if user_id != ADMIN_ID:
            return

        rows = list_accounts()

        if not rows:
            await query.edit_message_text(
                "📋 No hay cuentas SSH creadas.",
                reply_markup=back_admin_menu(),
            )
            return

        text = "📋 Cuentas SSH:\n\n"

        for row in rows:
            telegram_id, ssh_user, ssh_pass, plan, expire_date, max_connections = row

            if not ssh_pass:
                ssh_pass = "No guardada"

            text += (
                f"👤 SSH: {ssh_user}\n"
                f"🔑 Pass: {ssh_pass}\n"
                f"🆔 Telegram: {telegram_id}\n"
                f"📦 Plan: {plan}\n"
                f"📅 Expira: {expire_date}\n"
                f"🔌 Conexiones: {max_connections}\n\n"
            )

        await query.edit_message_text(
            text[:3900],
            reply_markup=back_admin_menu(),
        )

    elif data == "delete_ssh":
        if user_id != ADMIN_ID:
            return

        context.user_data.clear()
        context.user_data["step"] = "delete_ssh"

        await query.edit_message_text(
            "🗑 Escribe el usuario SSH que quieres eliminar:",
            reply_markup=back_admin_menu(),
        )



def get_user_accounts(telegram_id):
    db_file = globals().get("DB_FILE") or globals().get("DB_PATH") or globals().get("DATABASE") or "bot.db"

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT telegram_id, ssh_user, ssh_pass, plan, expire_date, max_connections
            FROM accounts
            WHERE telegram_id=?
        """, (telegram_id,))
        rows = cur.fetchall()
    except Exception:
        rows = []

    conn.close()
    return rows


async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_expired_accounts()

    user_id = update.effective_user.id
    text = update.message.text.strip()
    step = context.user_data.get("step")

    if step == "ask_username":
        username_base = text.lower()
        prefix = "darkzsaid-"

        if not valid_username(username_base):
            await update.message.reply_text(
                """❌ Usuario inválido.

Reglas:
- mínimo 3 caracteres
- máximo 16 caracteres
- sin espacios
- solo letras, números y _""",
                reply_markup=back_menu(),
            )
            return

        username = username_base if username_base.startswith(prefix) else prefix + username_base

        context.user_data["ssh_username"] = username
        context.user_data["step"] = "ask_password"

        await update.message.reply_text(
            """🔑 Ahora escribe la contraseña SSH.

Reglas:
- mínimo 4 caracteres
- sin espacios""",
            reply_markup=back_menu(),
        )
        return

    elif step == "ask_password":
        password = text

        if not valid_password(password):
            await update.message.reply_text(
                """❌ Contraseña inválida.

Reglas:
- mínimo 4 caracteres
- sin espacios""",
                reply_markup=back_menu(),
            )
            return

        username = context.user_data["ssh_username"]
        plan = "VIP" if is_vip(user_id) else "FREE"

        if plan == "VIP":
            days = get_setting("vip_days")
            connections = get_setting("vip_connections")
            max_accounts = get_setting("vip_max_accounts")
        else:
            days = get_setting("free_days")
            connections = get_setting("free_connections")
            max_accounts = get_setting("free_max_accounts")

        accounts = get_user_accounts(user_id)

        if len(accounts) >= int(max_accounts):
            await update.message.reply_text(
                """❌ Ya alcanzaste el máximo de cuentas permitidas.

Cuando tu cuenta venza, podrás crear otra.""",
                reply_markup=back_menu(),
            )
            context.user_data.clear()
            return

        expire_date = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d")

        try:
            create_linux_user(username, password, expire_date, connections)
            save_account(user_id, username, password, plan, expire_date, connections)

            dominio_flare = "bot-telegram.scionvps.fun"

            try:
                expire_show = datetime.strptime(expire_date, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                expire_show = expire_date

            mensaje_cuenta = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ CUENTA CREADA CON ÉXITO
Creado por @DarkZsaid
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 CREDENCIALES:
Usuario:  {username}
Password: {password}

📅 EXPIRACIÓN:
Fecha: {expire_show} ({days} días)
Conexiones: {connections}
Plan: {plan}

🌐 SERVIDOR:
IP:             {HOST}
Dominio Flare:  {dominio_flare}

🔌 PUERTOS ACTIVOS:
• SSH: {SSH_PORT}                  • System-DNS: 53
• SOCKS/PYTHON3: 80        • WEB/NGinx: 81
• SSL/TLS: {SSL_PORT}             • UDP-Custom: {UDP_CUSTOM}
• BadVPN: 7200             • BadVPN: 7300

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 CONFIGURACIONES DE CONEXIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 UDP HTTP Custom:
{HOST}:1-65535@{username}:{password}

🔹 SSL/TLS (SNI):
{HOST}:{SSL_PORT}@{username}:{password}

🔹 SOCKS/PYTHON3 Puerto 80 (IP):
{HOST}:80@{username}:{password}

🔹 SSH Dominio Cloudflare:
{dominio_flare}:80@{username}:{password}

🔹 SSH Cloudflare SSL/TLS:
{dominio_flare}:443@{username}:{password}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NS: —
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 Créditos restantes: 0/1
⏰ Regen: +1 crédito cada 24h
Creado por @DarkZsaid
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

            await update.message.reply_text(
                f"<pre>{html.escape(mensaje_cuenta)}</pre>",
                parse_mode="HTML",
            )

        except Exception as e:
            await update.message.reply_text(
                f"""❌ Error creando cuenta:
{e}""",
                reply_markup=back_menu(),
            )

        context.user_data.clear()
        return

    else:
        await update.message.reply_text("🤖 Usa /start para abrir el menú.")
        return


def main():

    init_db()
    update_db_columns()
    clean_expired_accounts()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))

    print(f"{BOT_NAME} iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()
