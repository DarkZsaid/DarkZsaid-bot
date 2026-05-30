#!/bin/bash

clear

ROJO="\e[31m"
VERDE="\e[32m"
AMARILLO="\e[33m"
CYAN="\e[36m"
BLANCO="\e[97m"
RESET="\e[0m"
BOLD="\e[1m"

REPO_URL="https://github.com/DarkZsaid/DarkZsaid-bot.git"
BOT_DIR="/opt/darkzsaid-bot"
SERVICE_NAME="darkzsaid-bot"

echo -e "${ROJO}════════════════════════════════════════════════════${RESET}"
echo -e "${BLANCO}${BOLD}        INSTALADOR BOT DARKZSAID                  ${RESET}"
echo -e "${ROJO}════════════════════════════════════════════════════${RESET}"
echo ""

if [[ "$(id -u)" -ne 0 ]]; then
    echo -e "${ROJO}Debes ejecutar como root.${RESET}"
    exit 1
fi

echo -e "${CYAN}Instalando dependencias...${RESET}"
apt update
apt install -y git curl wget nano python3 python3-pip python3-venv

echo ""
echo -e "${CYAN}Preparando instalación limpia del bot...${RESET}"

if [[ -d "$BOT_DIR" ]]; then
    FECHA=$(date +%Y%m%d-%H%M%S)
    echo -e "${AMARILLO}Ya existe $BOT_DIR. Creando backup...${RESET}"
    tar -czf "/root/darkzsaid-bot-before-install-$FECHA.tar.gz" "$BOT_DIR" 2>/dev/null || true
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    rm -rf "$BOT_DIR"
fi

echo ""
echo -e "${CYAN}Descargando bot desde GitHub...${RESET}"

git clone "$REPO_URL" "$BOT_DIR"

if [[ ! -d "$BOT_DIR" ]]; then
    echo -e "${ROJO}Error: no se pudo descargar el bot.${RESET}"
    exit 1
fi

cd "$BOT_DIR" || exit 1

echo ""
echo -e "${CYAN}Creando entorno Python...${RESET}"

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo -e "${AMARILLO}Configura TU bot de Telegram.${RESET}"
echo ""

read -p "Pega el TOKEN de tu bot Telegram: " BOT_TOKEN
read -p "Pega tu ID de Telegram administrador: " ADMIN_ID
read -p "IP o dominio de tu VPS: " HOST

if [[ -z "$BOT_TOKEN" || -z "$ADMIN_ID" || -z "$HOST" ]]; then
    echo -e "${ROJO}Token, ADMIN_ID o HOST vacío. Instalación cancelada.${RESET}"
    exit 1
fi

cat > "$BOT_DIR/.env" <<EOC
BOT_TOKEN="$BOT_TOKEN"
ADMIN_ID="$ADMIN_ID"

BOT_NAME="DarkZsaid SSH Bot"
PANEL_NAME="DarkZsaid"

HOST="$HOST"
SSH_PORT="22"
WS_PORT="80"
SSL_PORT="443"
UDP_CUSTOM="36712"
EOC

chmod 600 "$BOT_DIR/.env"

echo ""
echo -e "${CYAN}Creando servicio systemd...${RESET}"

cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOC
[Unit]
Description=DarkZsaid SSH Bot
After=network.target

[Service]
WorkingDirectory=$BOT_DIR
ExecStart=$BOT_DIR/venv/bin/python $BOT_DIR/bot.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOC

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo ""
echo -e "${CYAN}Instalando comando darkzsaidbot...${RESET}"

if [[ -f "$BOT_DIR/darkzsaidbot.sh" ]]; then
    chmod +x "$BOT_DIR/darkzsaidbot.sh"
    ln -sf "$BOT_DIR/darkzsaidbot.sh" /usr/local/bin/darkzsaidbot
    chmod +x /usr/local/bin/darkzsaidbot
fi


echo ""
echo -e "${VERDE}${BOLD}Bot instalado correctamente.${RESET}"
echo ""
echo -e "${AMARILLO}Comandos útiles:${RESET}"
echo "systemctl status darkzsaid-bot --no-pager"
echo "journalctl -u darkzsaid-bot -f"
echo "darkzsaidbot"
echo ""
