#!/usr/bin/env bash
# Programa la ingesta automática en el EC2 (cron). El EC2 está en UTC:
#   10:00 UTC = 05:00 Colombia  -> MariaDB a S3 (diario)
#   minuto 15 de cada hora      -> archivos a S3 (sync incremental)
set -euo pipefail
REPO="$HOME/proyecto2-bigdata-clima"
mkdir -p "$HOME/logs"

crontab - <<EOF
0 10 * * *  bash -c 'source $REPO/config.env && python3 $REPO/03-ingesta/ec2/ingesta_mariadb.py' >> $HOME/logs/ingesta_mariadb.log 2>&1
15 * * * *  bash -c 'source $REPO/config.env && bash $REPO/03-ingesta/ec2/ingesta_archivos.sh'   >> $HOME/logs/ingesta_archivos.log 2>&1
EOF
crontab -l
echo "Logs en $HOME/logs/. Para probar ya mismo, ejecute los comandos manualmente (ver README)."
