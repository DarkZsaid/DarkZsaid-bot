#!/bin/bash
set -u

REPO_URL="https://github.com/stevenjosecarcamo-star/DarkZsaid-bot.git"
APP_DIR="/opt/darkzsaid-bot"
TMP_DIR="/tmp/darkzsaid-bot-install"
SERVICE_NAME="darkzsaid-bot"

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

clear
echo "=============================================="
echo "        INSTALADOR BOT DARKZSAID"
echo "=============================================="
echo

if [ "$(id -u)" -ne 0 ]; then
  echo "Error: ejecuta este instalador como root."
  exit 1
fi

echo "Instalando dependencias..."
apt update -y
apt install -y git curl wget nano python3 python3-venv python3-pip

echo
echo "Deteniendo servicio anterior si existe..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

echo
echo "Preparando instalacion limpia..."
cd /root || exit 1

rm -rf "$TMP_DIR"
git clone "$REPO_URL" "$TMP_DIR" || {
  echo "Error: no se pudo clonar el bot desde GitHub."
  exit 1
}

if [ -d "$APP_DIR" ]; then
  BACKUP="${APP_DIR}.backup.$(date +%F_%H-%M-%S)"
  echo "Ya existe $APP_DIR. Creando backup en $BACKUP"
  mv "$APP_DIR" "$BACKUP"
fi

mv "$TMP_DIR" "$APP_DIR"
cd "$APP_DIR" || exit 1

echo
echo "Creando entorno Python..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip

if [ -f requirements.txt ]; then
  ./venv/bin/pip install -r requirements.txt
else
  ./venv/bin/pip install python-telegram-bot
fi

echo
echo "Verificando sintaxis del bot..."
./venv/bin/python -m py_compile bot.py || {
  echo "Error: bot.py tiene errores de sintaxis."
  exit 1
}

echo
echo "Creando servicio systemd..."
cat > /etc/systemd/system/${SERVICE_NAME}.service <<SERVICE
[Unit]
Description=DarkZsaid SSH Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/bot.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

chmod 644 /etc/systemd/system/${SERVICE_NAME}.service

echo
echo "Activando bot..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo
echo "Estado del bot:"
systemctl status "$SERVICE_NAME" --no-pager -l | head -40

echo
echo "=============================================="
echo " BOT DARKZSAID INSTALADO"
echo "=============================================="
echo "Ruta: $APP_DIR"
echo "Servicio: $SERVICE_NAME"
echo
echo "Comandos:"
echo "systemctl status darkzsaid-bot --no-pager -l"
echo "journalctl -u darkzsaid-bot --no-pager -n 50"
