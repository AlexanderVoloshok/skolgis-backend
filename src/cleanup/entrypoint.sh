#!/usr/bin/env bash
set -euo pipefail

python /cleanup/setup_cron.py

# стартуем cron (в Debian cron стартует как демон)
cron

# запускаем приложение (замени на свою команду)
exec "$@"
