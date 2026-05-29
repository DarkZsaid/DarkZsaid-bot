#!/bin/bash

echo "===== REVISANDO DARKZSAID BOT ====="

echo
echo "===== bot.py ====="
python3 -m py_compile bot.py && echo "OK bot.py" || exit 1

echo
echo "===== config.py ====="
if [ -f config.py ]; then
  python3 -m py_compile config.py && echo "OK config.py" || exit 1
else
  echo "config.py no existe, saltando..."
fi

echo
echo "===== install.sh ====="
bash -n install.sh && echo "OK install.sh" || exit 1

echo
echo "===== REVISION BOT COMPLETA OK ====="
