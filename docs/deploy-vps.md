# Деплой tutuorders на VPS

Продакшн: `/opt/tutuorders`, сервис `tutuorders-backend`, сайт через nginx (порт **3001**).  
Старый проект на том же VPS **не трогать**.

## Перед первым деплоем variant B

На сервере после `git pull` обязательно:

```bash
cd /opt/tutuorders/backend
source .venv/bin/activate
pip install -r requirements.txt
python -c "from app.db_migrate import run_pending_migrations; run_pending_migrations()"
```

Миграции `004`–`011` добавляют локации, словарь, планы закупки, распределение, метаданные планов.  
Без этого шага новые экраны упадут с ошибкой SQLite.

## Автодеплой (рекомендуется)

1. Настроить secrets в GitHub → Settings → Secrets → Actions:
   - `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, опционально `VPS_PORT`
2. Merge PR в `main` — workflow `.github/workflows/deploy-vps.yml` выполнит pull + restart + `npm run build`.

## Ручной деплой (после merge в main)

```bash
cd /opt/tutuorders
git fetch origin
git checkout main
git pull origin main
git log -1 --oneline

cd backend
source .venv/bin/activate
pip install -r requirements.txt
python -c "from app.db_migrate import run_pending_migrations; run_pending_migrations()"
sudo systemctl restart tutuorders-backend

cd ../frontend
npm ci
npm run build

sudo nginx -t && sudo systemctl reload nginx
```

В браузере: **Ctrl+F5**.

## Если на проде пустой «План закупки»

1. Убедитесь, что в `main` смержен PR с variant B и на VPS `git log -1` показывает свежий коммит.
2. Выполните миграции (команда выше) и `sudo systemctl restart tutuorders-backend`.
3. Пересоберите frontend: `npm run build` + reload nginx, в браузере **Ctrl+F5**.
4. В DevTools → Network откройте `GET /api/procurement/batches`:
   - **503** — не применены миграции;
   - **401** — включён `AUTH_ENABLED`, нужен вход / токен;
   - **404** — старый backend без новых роутов.

## YandexGPT (умный поиск на шаге «Проверка»)

На проде в шапке проверки должно быть **«локально + ИИ»**. Если **«только локально»** — backend не видит ключи.

Файл **`/opt/tutuorders/backend/.env`** (не в git). Важно: unit systemd должен либо иметь
`WorkingDirectory=/opt/tutuorders/backend`, либо ключи подхватятся из абсолютного пути к этому файлу
(после обновления `app/config.py`).

```env
YANDEX_FOLDER_ID=b1gxxxxxxxxxx
YANDEX_API_KEY=AQVNxxxxxxxx
YANDEX_MODEL_NAME=yandexgpt
YANDEX_TIMEOUT_SECONDS=25
```

После правки:

```bash
sudo systemctl restart tutuorders-backend
```

Проверка (с сервера или с ПК через curl к API):

```bash
curl -s http://127.0.0.1:8000/api/health
```

В ответе `"yandex": {"configured": true, ...}` — ИИ включён.

`folder_id` можно задать в `.env` или в БД (`settings`, ключ `folder_id`); API-ключ **только** в `.env`.

### Если в логах `unknown model 'gpt://yandexgpt-pro/latest'`

Это обычно означает, что в БД (`settings`) остался `model_name=yandexgpt-pro`, который перекрывает `.env`.

Проверка:

```bash
sqlite3 /opt/tutuorders/backend/app.db "SELECT key, value FROM settings WHERE key IN ('folder_id','model_name');"
```

Исправление:

```bash
sqlite3 /opt/tutuorders/backend/app.db "UPDATE settings SET value='yandexgpt' WHERE key='model_name';"
sudo systemctl restart tutuorders-backend
```

После этого `POST /api/procurement/batches/{id}/match` должен перестать падать в `procurement_ai_match http 404`.

### Если `configured: false`, а в `backend/.env` всё заполнено

1. Имена переменных **строго** такие (см. `.env.example`):
   `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `YANDEX_MODEL_NAME`.
2. На сервере посмотрите блок `"env"` в `/api/health`:
   - `root_env_exists: true` и пустые ключи в `/opt/tutuorders/.env` — удалите корневой `.env` или перенесите ключи в `backend/.env`.
   - `yandex_api_key_in_os_env: true` и `yandex_api_key_os_nonempty: false` — в **systemd** задан пустой `YANDEX_API_KEY`; уберите строку из unit или добавьте `EnvironmentFile=/opt/tutuorders/backend/.env`.
3. Диагностика в shell (значения ключей не печатаются):

```bash
cd /opt/tutuorders/backend
source .venv/bin/activate
python -c "from app.config import ENV_FILES, settings; print('files', ENV_FILES); print('key_ok', bool(settings.yandex_api_key)); print('folder_ok', bool(settings.yandex_folder_id))"
grep -E '^YANDEX_' .env | cut -d= -f1
systemctl cat tutuorders-backend | grep -iE 'Environment|YANDEX'
```

## Проверка после деплоя

| Проверка | Ожидание |
|----------|----------|
| Главная | открывается **План закупки** |
| Прайсы | загрузка файла → результат под полем файла, список «нет в прайсе» по именам продуктов |
| Словарь | «Найти в прайсе», «Изменить» название |
| `GET /api/health` | OK |

## Откат

```bash
cd /opt/tutuorders
git log -5 --oneline
git checkout <предыдущий-коммит>
cd backend && source .venv/bin/activate && sudo systemctl restart tutuorders-backend
cd ../frontend && npm run build && sudo systemctl reload nginx
```

## Локальная публикация в Git

```powershell
.\scripts\publish.ps1 -Message "краткое описание"
```

Скрипт: commit → push → PR в `main` (браузер или `gh`).
