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

    hash_result = subprocess.run(
        ["openssl", "passwd", "-6", password],
        capture_output=True,
        text=True,
        check=True,
    )
    password_hash = hash_result.stdout.strip()
    subprocess.run(["usermod", "-p", password_hash, username], check=True)

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



def is_admin_user(telegram_id):
    try:
        telegram_id = int(telegram_id)
    except Exception:
        return False

    admins = []

    for name in ("ADMIN_ID", "OWNER_ID"):
        val = globals().get(name)
        if val:
            try:
                admins.append(int(val))
            except Exception:
                pass

    val = globals().get("ADMIN_IDS")
    if val:
        if isinstance(val, (list, tuple, set)):
            for x in val:
                try:
                    admins.append(int(x))
                except Exception:
                    pass
        else:
            for x in str(val).replace(";", ",").split(","):
                x = x.strip()
                if x:
                    try:
                        admins.append(int(x))
                    except Exception:
                        pass

    return telegram_id in admins


def main_menu(user_id):
    keyboard = [
        [InlineKeyboardButton("👤 Crear SSH", callback_data="create_ssh")],
        [
            InlineKeyboardButton("📋 Mi cuenta", callback_data="active_accounts"),
            InlineKeyboardButton("💳 Tus créditos", callback_data="my_account"),
        ],
        [InlineKeyboardButton("🔄 Renovar cuenta", callback_data="renew_account")],
    ]
    if is_admin_user(user_id):
        keyboard.append([InlineKeyboardButton("🔥 Panel DarkZsaid", callback_data="admin_panel")])

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



# ===== DARKZSAID DOMAIN CONFIG =====
DOMAIN_FILE = "/opt/darkzsaid-bot/domain_cloudflare.txt"
DEFAULT_CLOUDFLARE_DOMAIN = "bot-telegram.scionvps.fun"

def get_cloudflare_domain():
    try:
        with open(DOMAIN_FILE, "r") as f:
            domain = f.read().strip()
            if domain:
                return domain
    except Exception:
        pass
    return DEFAULT_CLOUDFLARE_DOMAIN

def save_cloudflare_domain(domain):
    domain = domain.strip()
    domain = domain.replace("https://", "").replace("http://", "").strip("/")
    if not domain or " " in domain or "." not in domain:
        return False
    with open(DOMAIN_FILE, "w") as f:
        f.write(domain + "\n")
    return True
# ===== END DARKZSAID DOMAIN CONFIG =====

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
            InlineKeyboardButton("🔄 Renovar cuenta", callback_data="renew_account"),
        ],
        [InlineKeyboardButton("🏠 Menú principal", callback_data="back")],
    ]

    keyboard.append([InlineKeyboardButton("Cambiar dominio Cloudflare", callback_data="set_domain")])
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





def get_credit_status(telegram_id):
    try:
        if is_admin_user(telegram_id):
            return "1/1 🟢"
    except Exception:
        pass

    try:
        accounts = get_user_accounts(telegram_id)
        if len(accounts) >= 1:
            return "0/1 ⚫"
        return "1/1 🟢"
    except Exception:
        return "1/1 🟢"


    try:
        accounts = get_user_accounts(telegram_id)
        if (not is_admin_user(user_id)) and len(accounts) >= 1:
            return "0/1 ⚫"
        return "1/1 🟢"
    except Exception:
        return "1/1 🟢"




def get_all_registered_ssh_accounts():
    import sqlite3
    import os
    import glob

    candidates = []

    for var in ("DB_FILE", "DB_PATH", "DATABASE", "DB_NAME"):
        val = globals().get(var)
        if val:
            candidates.append(str(val))

    candidates += glob.glob("/opt/darkzsaid-bot/*.db")

    seen = []
    for db_file in candidates:
        if db_file and db_file not in seen:
            seen.append(db_file)

    for db_file in seen:
        if not os.path.exists(db_file):
            continue

        try:
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
            if not cur.fetchone():
                conn.close()
                continue

            cur.execute("PRAGMA table_info(accounts)")
            cols = [row[1] for row in cur.fetchall()]

            if "ssh_user" not in cols:
                conn.close()
                continue

            select_cols = ["ssh_user"]
            if "ssh_pass" in cols:
                select_cols.append("ssh_pass")
            if "expire_date" in cols:
                select_cols.append("expire_date")
            if "plan" in cols:
                select_cols.append("plan")

            cur.execute(f"SELECT {', '.join(select_cols)} FROM accounts ORDER BY ssh_user ASC")
            rows = cur.fetchall()
            conn.close()

            users = []
            for row in rows:
                item = {}
                for i, col in enumerate(select_cols):
                    item[col] = row[i]
                users.append(item)

            return users

        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            continue

    return []


def build_delete_ssh_text_and_menu():
    users = get_all_registered_ssh_accounts()

    if not users:
        text = "🗑 ELIMINAR SSH\n\nNo hay cuentas registradas."
        keyboard = [
            [InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_panel")]
        ]
        return text, InlineKeyboardMarkup(keyboard)

    lines = ["🗑 ELIMINAR SSH", "", "Selecciona el número del usuario que deseas borrar:", ""]

    keyboard = []

    for i, u in enumerate(users, start=1):
        ssh_user = u.get("ssh_user", "")
        expire = u.get("expire_date", "-")
        plan = u.get("plan", "-")

        lines.append(f"[{i}] {ssh_user} | {plan} | vence: {expire}")

        keyboard.append([
            InlineKeyboardButton(f"[{i}] 🗑 {ssh_user}", callback_data=f"delssh:{ssh_user}")
        ])

    keyboard.append([
        InlineKeyboardButton("🧨 Borrar todas las cuentas registradas", callback_data="delete_all_ssh")
    ])
    keyboard.append([
        InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_panel")
    ])

    return "\\n".join(lines), InlineKeyboardMarkup(keyboard)


def delete_registered_ssh_user(ssh_user):
    # Borra de Linux y de la base del bot. No toca root ni servicios SSH.
    delete_linux_user(ssh_user)
    delete_account_db(ssh_user)


def delete_all_registered_ssh_users():
    users = get_all_registered_ssh_accounts()
    deleted = []

    for u in users:
        ssh_user = u.get("ssh_user", "").strip()

        if not ssh_user:
            continue

        # Protección básica para no tocar usuarios del sistema por accidente
        if ssh_user in ("root", "ubuntu", "admin"):
            continue

        try:
            delete_registered_ssh_user(ssh_user)
            deleted.append(ssh_user)
        except Exception:
            pass

    return deleted



def get_active_account_remaining_text(telegram_id):
    from datetime import datetime

    try:
        accounts = get_user_accounts(telegram_id)
    except Exception:
        accounts = []

    if not accounts:
        return None, "No tienes una cuenta SSH activa."

    row = accounts[0]

    ssh_user = "-"
    expire_date = "-"

    try:
        # Si viene como tupla: telegram_id, ssh_user, ssh_pass, plan, expire_date, max_connections
        ssh_user = row[1]
        expire_date = row[4]
    except Exception:
        try:
            ssh_user = row.get("ssh_user", "-")
            expire_date = row.get("expire_date", "-")
        except Exception:
            pass

    try:
        exp = datetime.strptime(str(expire_date), "%Y-%m-%d")
        now = datetime.now()
        diff = exp - now

        if diff.total_seconds() <= 0:
            restante = "ya venció"
        else:
            horas = int(diff.total_seconds() // 3600)
            minutos = int((diff.total_seconds() % 3600) // 60)
            restante = f"{horas}h {minutos}m"
    except Exception:
        restante = "no disponible"

    msg = f"""🔄 RENOVAR CUENTA

👤 Usuario activo: {ssh_user}
📅 Vence: {expire_date}
⏳ Tiempo restante: {restante}

Por ahora tu cuenta sigue activa.
Cuando venza, podrás crear o renovar otra cuenta."""
    return ssh_user, msg



def format_remaining_from_expire(expire_date):
    from datetime import datetime

    try:
        exp = datetime.strptime(str(expire_date), "%Y-%m-%d")
        now = datetime.now()
        diff = exp - now

        if diff.total_seconds() <= 0:
            return "ya venció"

        horas = int(diff.total_seconds() // 3600)
        minutos = int((diff.total_seconds() % 3600) // 60)

        if horas >= 24:
            dias = horas // 24
            horas_rest = horas % 24
            return f"{dias}d {horas_rest}h {minutos}m"

        return f"{horas}h {minutos}m"
    except Exception:
        return "no disponible"


def build_active_accounts_text(telegram_id):
    accounts = get_user_accounts(telegram_id)

    if not accounts:
        return """📋 TUS USUARIOS SSH ACTIVOS

No tienes usuarios SSH activos.

Usa /start y toca Crear SSH para crear una cuenta."""

    lines = ["📋 TUS USUARIOS SSH ACTIVOS", ""]

    for i, row in enumerate(accounts, start=1):
        try:
            ssh_user = row[1]
            ssh_pass = row[2]
            plan = row[3]
            expire_date = row[4]
            max_connections = row[5]
        except Exception:
            ssh_user = "-"
            ssh_pass = "-"
            plan = "-"
            expire_date = "-"
            max_connections = "-"

        restante = format_remaining_from_expire(expire_date)

        lines.append(f"[{i}] 👤 {ssh_user}")
        lines.append(f"🔑 Password: {ssh_pass}")
        lines.append(f"📅 Expira: {expire_date}")
        lines.append(f"⏳ Restante: {restante}")
        lines.append("")

    return "\n".join(lines)


def build_credits_text(telegram_id):
    accounts = get_user_accounts(telegram_id)

    if accounts:
        try:
            expire_date = accounts[0][4]
            ssh_user = accounts[0][1]
        except Exception:
            expire_date = "-"
            ssh_user = "-"

        restante = format_remaining_from_expire(expire_date)

        return f"""💳 TUS CRÉDITOS

Disponibles: 0/1 ⚫
👤 Usuario activo: {ssh_user}
⏳ Próximo crédito en: {restante}

Cada cuenta SSH consume 1 crédito.
Puedes crear otra cuenta cuando venza tu cuenta activa."""

    return """💳 TUS CRÉDITOS

Disponibles: 1/1 🟢
⏳ Próximo crédito: disponible ahora

Puedes crear 1 cuenta SSH.
Cada cuenta es válida por 3 días."""



async def set_domain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("Acceso denegado. Solo administrador.")
        return

    if not context.args:
        actual = get_cloudflare_domain()
        await update.message.reply_text(
            f"Dominio Cloudflare actual:\n{actual}\n\n"
            "Para cambiarlo usa:\n"
            "/dominio nuevo-dominio.com"
        )
        return

    nuevo = context.args[0].strip()

    if not save_cloudflare_domain(nuevo):
        await update.message.reply_text(
            "Dominio invalido.\n\n"
            "Ejemplo correcto:\n"
            "/dominio mi-dominio.com"
        )
        return

    await update.message.reply_text(
        f"Dominio Cloudflare actualizado correctamente:\n{get_cloudflare_domain()}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_expired_accounts()
    context.user_data.clear()
    user_id = update.effective_user.id
    creditos_txt = get_credit_status(user_id)

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
💳 Créditos: {creditos_txt}

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
        creditos_txt = get_credit_status(user_id)

        await query.edit_message_text(
            f"""
━━━━━━━━━━━━━━━━━━━━
     ⚡ DARKZSAID SSH BOT ⚡
  Panel automático de cuentas SSH
       Creado por @DarkZsaid
━━━━━━━━━━━━━━━━━━━━

👤 Nombre: {tg_name}
🆔 Usuario: @{tg_username}
💳 Créditos: {creditos_txt}

🌐 Elige acción:
📅 Cuentas válidas por 3 días
""",
            reply_markup=main_menu(user_id),
        )

    elif data == "create_ssh":
        context.user_data.clear()

        accounts = get_user_accounts(user_id)

        if (not is_admin_user(user_id)) and len(accounts) >= 1:
            await query.edit_message_text(
                "❌ Sin créditos.\n\n"
                "⏳ Ya tienes una cuenta activa.\n"
                "📅 Podrás crear otra cuando se venza la cuenta actual.\n\n"
                "Usa /start para volver al menú."
            )
            return

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

    elif data == "active_accounts":
        info = build_active_accounts_text(user_id)

        await query.edit_message_text(
            info,
            reply_markup=back_menu(),
        )

    elif data == "my_account":
        info = build_credits_text(user_id)

        await query.edit_message_text(
            info,
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
📦 
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


    elif data == "renew_account":
        ssh_user, msg = get_active_account_remaining_text(user_id)

        await query.edit_message_text(
            msg,
            reply_markup=back_menu(),
        )

    elif data == "admin_panel":
        if not is_admin_user(user_id):
            await query.edit_message_text(
                "⛔ Acceso denegado. Esta opción es solo para administrador.",
                reply_markup=back_menu(),
            )
            return

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


    elif data == "set_domain":
        if user_id != ADMIN_ID:
            return

        dominio_actual = get_cloudflare_domain()
        text = f"""CONFIGURAR DOMINIO CLOUDFLARE

Dominio actual:
{dominio_actual}

Para cambiarlo escribe:

/dominio nuevo-dominio.com

Ejemplo:
/dominio mi-vps.cloudflare.com
"""
        await query.edit_message_text(text, reply_markup=back_admin_menu())

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


    elif data.startswith("delssh:"):
        ssh_user = data.split(":", 1)[1].strip()

        try:
            delete_registered_ssh_user(ssh_user)
            msg = f"✅ Usuario eliminado: {ssh_user}\n\n"
        except Exception as e:
            msg = f"❌ Error eliminando {ssh_user}:\n{e}\n\n"

        text_del, menu_del = build_delete_ssh_text_and_menu()
        await query.edit_message_text(
            msg + text_del,
            reply_markup=menu_del,
        )

    elif data == "delete_all_ssh":
        deleted = delete_all_registered_ssh_users()

        if deleted:
            msg = "✅ Cuentas eliminadas:\n" + "\n".join(f"- {u}" for u in deleted) + "\n\n"
        else:
            msg = "ℹ️ No había cuentas registradas para borrar.\n\n"

        text_del, menu_del = build_delete_ssh_text_and_menu()
        await query.edit_message_text(
            msg + text_del,
            reply_markup=menu_del,
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
        context.user_data.clear()
        text_del, menu_del = build_delete_ssh_text_and_menu()
        await query.edit_message_text(
            text_del,
            reply_markup=menu_del,
        )




def get_user_accounts(telegram_id):
    import sqlite3
    import os
    import glob
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")

    candidates = []

    for var in ("DB_FILE", "DB_PATH", "DATABASE", "DB_NAME"):
        val = globals().get(var)
        if val:
            candidates.append(str(val))

    candidates += glob.glob("/opt/darkzsaid-bot/*.db")

    seen = []
    for db_file in candidates:
        if db_file and db_file not in seen:
            seen.append(db_file)

    for db_file in seen:
        if not os.path.exists(db_file):
            continue

        try:
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
            if not cur.fetchone():
                conn.close()
                continue

            cur.execute("PRAGMA table_info(accounts)")
            cols = [row[1] for row in cur.fetchall()]

            if "telegram_id" not in cols:
                conn.close()
                continue

            wanted = ["telegram_id", "ssh_user", "ssh_pass", "plan", "expire_date", "max_connections"]
            select_cols = [c for c in wanted if c in cols]

            if not select_cols:
                select_cols = ["*"]

            sql = f"SELECT {', '.join(select_cols)} FROM accounts WHERE telegram_id=?"
            params = [telegram_id]

            if "expire_date" in cols:
                sql += " AND expire_date >= ?"
                params.append(today)

            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            conn.close()

            if rows:
                return rows

        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            continue

    return []


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
        if is_admin_user(user_id):
            plan = "ADMIN"
            days = 30
            connections = get_setting("vip_connections")
            max_accounts = 999999
        else:
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

        if (not is_admin_user(user_id)) and len(accounts) >= 1:
            await update.message.reply_text(
                """❌ Ya usaste tu crédito disponible.

Cuando tu cuenta venza, podrás crear otra cuenta.""",
                reply_markup=back_menu(),
            )
            context.user_data.clear()
            return

        expire_date = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d")

        try:
            create_linux_user(username, password, expire_date, connections)
            save_account(user_id, username, password, plan, expire_date, connections)

            dominio_flare = get_cloudflare_domain()

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
💳 Créditos restantes: 0/1
⏰ Regen: +1 crédito cuando venza tu cuenta
📅 Tiempo de espera: 3 días
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
    app.add_handler(CommandHandler("dominio", set_domain_command))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))
    print(f"{BOT_NAME} iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()
