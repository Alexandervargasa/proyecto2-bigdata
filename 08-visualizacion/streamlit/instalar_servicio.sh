#!/usr/bin/env bash
# Ejecutar en el EC2: deja Streamlit corriendo como servicio (arranca solo si
# el EC2 se reinicia). Requiere API_URL en config.env.
set -euo pipefail
REPO="$HOME/proyecto2-bigdata-clima"
source "$REPO/config.env"
: "${API_URL:?Agregue export API_URL=... a config.env (lo imprimió desplegar_api.sh)}"
pip3 install --user -q -r "$REPO/08-visualizacion/streamlit/requirements.txt"

sudo tee /etc/systemd/system/streamlit-clima.service >/dev/null <<EOF
[Unit]
Description=Streamlit clima Colombia
After=network-online.target

[Service]
User=ec2-user
WorkingDirectory=$REPO/08-visualizacion/streamlit
Environment=API_URL=$API_URL
ExecStart=/home/ec2-user/.local/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now streamlit-clima
sleep 3 && systemctl --no-pager status streamlit-clima | head -5
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
echo "App: http://$IP:8501"
