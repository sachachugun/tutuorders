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
