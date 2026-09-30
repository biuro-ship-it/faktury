#!/usr/bin/env bash
# Wdrożenie na mydevil (faktury.pluszek.pl). Uruchamiać z Git Bash w katalogu projektu:
#     ./deploy.sh
# Kroki: testy → build frontu → wysyłka kodu → pip → migracje Alembic → restart → sprawdzenie.
# Plik backend/.env na serwerze NIE jest nadpisywany (tworzony raz, ręcznie).
set -euo pipefail

SERWER="Pluszek@s61.mydevil.net"
DOMENA="faktury.pluszek.pl"
ZDALNIE="domains/$DOMENA"
KATALOG="$(cd "$(dirname "$0")" && pwd)"

echo "==> 1/6 Testy backendu (niezmiennik musi być zielony przed wdrożeniem)"
(cd "$KATALOG/backend" && .venv/Scripts/python -m pytest -q)

echo "==> 2/6 Build frontu"
(cd "$KATALOG/frontend" && npm run build)

echo "==> 3/6 Pakowanie i wysyłka"
PACZKA="$(mktemp -d)"
cp -r "$KATALOG/backend/app" "$KATALOG/backend/alembic" "$KATALOG/backend/alembic.ini" \
      "$KATALOG/backend/requirements.txt" "$PACZKA/"
cp -r "$KATALOG/frontend/dist" "$PACZKA/static"
cp "$KATALOG/backend/passenger_wsgi.py" "$PACZKA/"
find "$PACZKA" -name __pycache__ -type d -prune -exec rm -rf {} +
tar -czf "$PACZKA.tgz" -C "$PACZKA" .
ssh "$SERWER" "rm -rf ~/tmp/faktury-deploy && mkdir -p ~/tmp/faktury-deploy"
scp -q "$PACZKA.tgz" "$SERWER:tmp/faktury-deploy/paczka.tgz"
rm -rf "$PACZKA" "$PACZKA.tgz"

echo "==> 4/6 Rozpakowanie, zależności, migracje"
ssh "$SERWER" bash -s <<EOF
set -euo pipefail
cd ~/tmp/faktury-deploy && tar -xzf paczka.tgz && rm paczka.tgz
mv passenger_wsgi.py ~/$ZDALNIE/public_python/passenger_wsgi.py
# --delete usuwa pliki, których nie ma już w repo; .env i logi zostają nietknięte.
rsync -a --delete --exclude .env ./ ~/$ZDALNIE/backend/
cd ~/$ZDALNIE
.venv/bin/pip install -q -r backend/requirements.txt
cd backend && ../.venv/bin/python -m alembic upgrade head
rm -rf ~/tmp/faktury-deploy
EOF

echo "==> 5/6 Restart aplikacji"
ssh "$SERWER" "devil www restart $DOMENA"

echo "==> 6/6 Sprawdzenie"
KOD=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMENA/api/me")
STRONA=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMENA/")
echo "   https://$DOMENA/        → $STRONA (oczekiwane 200)"
echo "   https://$DOMENA/api/me  → $KOD (oczekiwane 401 — bez tokenu)"
if [ "$STRONA" != "200" ] || [ "$KOD" != "401" ]; then
  echo "!! Coś nie tak — logi: ssh $SERWER 'tail -50 $ZDALNIE/logs/error.log'"
  exit 1
fi
echo "==> Gotowe."
