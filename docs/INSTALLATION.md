# Installation Guide
1. **Clone**: `git clone git@github.com:bhadip/aegis.git && cd aegis`
2. **Config**: Create `.env` with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
3. **Build**: `docker compose up -d --build`
4. **Access**: Dashboard at `http://<YOUR_HOST_IP>:8000`. MT5 VNC at `http://<YOUR_HOST_IP>:9091`.
5. **MT5 Setup**: Allow WebRequest for `http://<YOUR_HOST_IP>:8000`. Drag `AEGIS_Captain` to `.ND` chart.
