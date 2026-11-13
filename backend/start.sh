#!/bin/sh
# Railway startup:
#   1. migrate  2. ensure superuser  3. gunicorn in background (healthcheck passes)
#   4. seed the prior-deal ledger when empty  5. analysis worker  6. wait on gunicorn

echo "=== Mindari / Deal Analysis starting ==="
if [ -z "$SECRET_KEY" ] && [ -z "$DATABASE_URL" ] && [ -z "$RAILWAY_SERVICE_ID" ]; then
    export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
fi
# Uploaded files: on Railway, attach a Volume to this service and mount it at /data
if [ -z "$MEDIA_ROOT" ] && [ -d /data ]; then export MEDIA_ROOT=/data/media; fi
[ -n "$MEDIA_ROOT" ] && mkdir -p "$MEDIA_ROOT" 2>/dev/null
echo "File storage: ${S3_BUCKET:+bucket $S3_BUCKET}${S3_BUCKET:-${MEDIA_ROOT:-container disk (not persistent - attach a Volume at /data)}}"

python -u manage.py migrate --noinput 2>&1 || echo "!!! migrate failed"

python -u manage.py shell 2>&1 << 'PYEOF'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email, pw = os.environ.get('DJANGO_SUPERUSER_EMAIL', ''), os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
if email and pw:
    if not User.objects.filter(email=email).exists():
        User.objects.create_superuser(email=email, password=pw, full_name=os.environ.get('DJANGO_SUPERUSER_FULL_NAME', 'Admin'))
        print(f'Superuser created: {email}')
    else:
        print(f'Superuser already exists: {email}')
else:
    print('DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD not set — skipping superuser')
PYEOF

# gthread workers keep long uploads alive; analyses never run inside a request
gunicorn mindari.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 8 --worker-class gthread \
    --timeout 600 --access-logfile - --error-logfile - --log-level info &
GUNICORN_PID=$!
sleep 3

python -u manage.py seed_ledger --if-empty 2>&1 || echo "!!! ledger seed failed"

echo "--- Starting analysis worker ---"
python -u manage.py analysis_worker 2>&1 &

wait $GUNICORN_PID
