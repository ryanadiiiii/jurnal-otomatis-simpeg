#!/bin/bash
# ============================================
# SIMPEG Jurnal Harian Otomatis
# Script Deploy ke Oracle Cloud Free Tier
# ============================================
# Jalankan script ini di server Oracle Cloud:
#   bash deploy.sh
# ============================================

set -e

echo "============================================"
echo "  SIMPEG Jurnal Harian Otomatis"
echo "  Auto Deploy Script untuk Oracle Cloud"
echo "============================================"
echo ""

# 1. Update sistem
echo "[1/7] Mengupdate sistem..."
sudo apt-get update -y
sudo apt-get upgrade -y

# 2. Install Python 3.12 dan dependencies
echo "[2/7] Menginstall Python dan dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv git libgl1 libglib2.0-0

# 3. Clone repository
echo "[3/7] Mendownload kode dari GitHub..."
cd /home/ubuntu
if [ -d "jurnal-otomatis-simpeg" ]; then
    echo "  Folder sudah ada, mengupdate..."
    cd jurnal-otomatis-simpeg
    git pull
else
    git clone https://github.com/ryanadiiiii/jurnal-otomatis-simpeg.git
    cd jurnal-otomatis-simpeg
fi

# 4. Setup virtual environment
echo "[4/7] Membuat Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 5. Install Python packages
echo "[5/7] Menginstall Python packages (ini agak lama ~3 menit)..."
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium --with-deps

# 6. Buat file .env
echo "[6/7] Membuat file konfigurasi .env..."
if [ ! -f .env ]; then
    echo "# SIMPEG Jurnal Harian Otomatis" > .env
    echo "# Isi data di bawah ini:" >> .env
    echo "" >> .env
    
    read -p "Masukkan NIP Anda: " NIP_INPUT
    echo "SIMPEG_NIP=$NIP_INPUT" >> .env
    
    read -sp "Masukkan Password SIMPEG: " PASS_INPUT
    echo ""
    echo "SIMPEG_PASSWORD=$PASS_INPUT" >> .env
    
    read -p "Masukkan Telegram Bot Token: " TOKEN_INPUT
    echo "TELEGRAM_BOT_TOKEN=$TOKEN_INPUT" >> .env
    
    read -p "Masukkan Telegram Chat ID: " CHATID_INPUT
    echo "TELEGRAM_CHAT_ID=$CHATID_INPUT" >> .env
    
    echo "DRY_RUN=False" >> .env
    
    echo "  File .env berhasil dibuat!"
else
    echo "  File .env sudah ada, dilewati."
fi

# 7. Setup cron job (Senin-Jumat jam 08:00 WIB = 01:00 UTC)
echo "[7/7] Mendaftarkan jadwal cron (Senin-Jumat 08:00 WIB)..."

CRON_CMD="0 1 * * 1-5 cd /home/ubuntu/jurnal-otomatis-simpeg && /home/ubuntu/jurnal-otomatis-simpeg/venv/bin/python scheduler.py >> /home/ubuntu/jurnal-otomatis-simpeg/cron.log 2>&1"

# Cek apakah cron sudah ada
(crontab -l 2>/dev/null | grep -v "scheduler.py"; echo "$CRON_CMD") | crontab -

echo ""
echo "============================================"
echo "  ✅ DEPLOY BERHASIL!"
echo "============================================"
echo ""
echo "Bot akan jalan otomatis setiap:"
echo "  Senin-Jumat pukul 08:00 WIB"
echo ""
echo "Untuk test sekarang (dry run):"
echo "  cd /home/ubuntu/jurnal-otomatis-simpeg"
echo "  source venv/bin/activate"
echo "  python scheduler.py --dry-run"
echo ""
echo "Untuk test sungguhan:"
echo "  python scheduler.py"
echo ""
echo "Cek log:"
echo "  tail -f /home/ubuntu/jurnal-otomatis-simpeg/cron.log"
echo ""
echo "============================================"
