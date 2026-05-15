#!/bin/bash

ROJO="\e[31m"
VERDE="\e[32m"
AMARILLO="\e[33m"
CYAN="\e[36m"
BLANCO="\e[97m"
RESET="\e[0m"
BOLD="\e[1m"

SERVICE_NAME="darkzsaid-bot"
BOT_DIR="/opt/darkzsaid-bot"

pausa() {
    echo ""
    read -p "Presiona ENTER para continuar..."
}

titulo() {
    clear
    echo -e "${ROJO}════════════════════════════════════════════${RESET}"
    echo -e "${BLANCO}${BOLD}        DARKZSAID BOT MANAGER              ${RESET}"
    echo -e "${ROJO}════════════════════════════════════════════${RESET}"
    echo ""
}

estado_bot() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${VERDE}ACTIVO${RESET}"
    else
        echo -e "${ROJO}DETENIDO${RESET}"
    fi
}

iniciar_bot() {
    titulo
    echo -e "${CYAN}Iniciando BOT DARKZSAID...${RESET}"
    systemctl start "$SERVICE_NAME"
    sleep 1
    echo ""
    echo -e "${AMARILLO}Estado actual:${RESET} $(estado_bot)"
    pausa
}

detener_bot() {
    titulo
    echo -e "${CYAN}Deteniendo BOT DARKZSAID...${RESET}"
    systemctl stop "$SERVICE_NAME"
    sleep 1
    echo ""
    echo -e "${AMARILLO}Estado actual:${RESET} $(estado_bot)"
    pausa
}

reiniciar_bot() {
    titulo
    echo -e "${CYAN}Reiniciando BOT DARKZSAID...${RESET}"
    systemctl restart "$SERVICE_NAME"
    sleep 1
    echo ""
    echo -e "${AMARILLO}Estado actual:${RESET} $(estado_bot)"
    pausa
}

eliminar_bot() {
    titulo
    echo -e "${ROJO}ATENCIÓN: Esto eliminará el BOT DARKZSAID de esta VPS.${RESET}"
    echo ""
    echo "Se eliminará:"
    echo "- Servicio systemd: $SERVICE_NAME"
    echo "- Carpeta: $BOT_DIR"
    echo "- Comando: darkzsaidbot"
    echo ""
    read -p "Escribe ELIMINAR para confirmar: " CONFIRMAR

    if [[ "$CONFIRMAR" != "ELIMINAR" ]]; then
        echo ""
        echo -e "${AMARILLO}Cancelado.${RESET}"
        pausa
        return
    fi

    echo ""
    echo -e "${CYAN}Deteniendo servicio...${RESET}"
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true

    echo -e "${CYAN}Eliminando servicio...${RESET}"
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload

    echo -e "${CYAN}Eliminando carpeta del bot...${RESET}"
    rm -rf "$BOT_DIR"

    echo -e "${CYAN}Eliminando comando global...${RESET}"
    rm -f /usr/local/bin/darkzsaidbot

    echo ""
    echo -e "${VERDE}BOT DARKZSAID eliminado correctamente.${RESET}"
    echo ""
    exit 0
}

while true; do
    titulo
    echo -e "${AMARILLO}Estado actual:${RESET} $(estado_bot)"
    echo ""
    echo -e "${ROJO}[01]${RESET} ${CYAN}➜${RESET} ${BLANCO}INICIAR BOT DARKZSAID${RESET}"
    echo -e "${ROJO}[02]${RESET} ${CYAN}➜${RESET} ${BLANCO}DETENER BOT DARKZSAID${RESET}"
    echo -e "${ROJO}[03]${RESET} ${CYAN}➜${RESET} ${BLANCO}REINICIAR BOT DARKZSAID${RESET}"
    echo -e "${ROJO}[04]${RESET} ${CYAN}➜${RESET} ${ROJO}ELIMINAR BOT DARKZSAID${RESET}"
    echo -e "${ROJO}[00]${RESET} ${CYAN}➜${RESET} ${BLANCO}SALIR${RESET}"
    echo ""
    read -p "Selecciona una opción: " opc

    case "$opc" in
        1|01) iniciar_bot ;;
        2|02) detener_bot ;;
        3|03) reiniciar_bot ;;
        4|04) eliminar_bot ;;
        0|00) clear; exit 0 ;;
        *) echo -e "${ROJO}Opción inválida.${RESET}"; sleep 1 ;;
    esac
done
