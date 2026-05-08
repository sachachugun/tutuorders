# tutuorders

MVP-сервис для закупщика: загрузка прайсов поставщиков, разбор текстового заказа, сопоставление позиций, расчет сумм и экспорт в Excel.

## Стек

- Backend: `FastAPI`, `SQLAlchemy`, `SQLite`, `httpx`, `openpyxl`, `xlrd`
- Frontend: `React`, `Vite`, `TypeScript`
- Infra: `systemd` + `nginx` на VPS
- LLM: `YandexGPT` (с fail-safe fallback без ИИ)

## Окружения

- Локальная разработка (корень проекта):  
  `C:\Users\chugi\OneDrive\Документы\папочка рабочая\Документы\BD\AI\Cursor`
- Локальный frontend: `http://localhost:5173`
- Локальный backend: `http://127.0.0.1:8000`

- Продакшн (второй проект на VPS):  
  путь: `/opt/tutuorders`  
  backend service: `tutuorders-backend`  
  backend слушает: `127.0.0.1:8000`  
  внешний доступ: `http://EXTERNAL_IP:3001` (через `nginx`)

## Важно по VPS

На VPS есть 2 проекта. Работать только с `tutuorders` в `/opt/tutuorders`.  
Старый проект не трогать.

## Авторизация и доступ

- Внешний доступ закрыт через `nginx basic auth` (логин/пароль на вход в сайт).
- Добавлен запрет индексации:
  - заголовок `X-Robots-Tag: noindex, nofollow, noarchive, nosnippet, noimageindex`
  - `robots.txt` с `Disallow: /`
- Внутренний app-auth поддерживается кодом backend, но может быть отключен флагом `AUTH_ENABLED=false`.

## Экраны и логика

## 1) Прайсы

Назначение: управление карточками поставщиков и загрузка прайсов.

- Карточка поставщика:
  - редактирование `name`, `min_order_amount`
  - сохраняется отдельно от загрузки файла
- Загрузка прайса:
  - формат: `A=название`, `B=единица`, `C=цена`
  - поддержка `.xls/.xlsx`
  - лимит: до `500` строк
  - при новой загрузке прайс поставщика **полностью заменяет** старый
- Очистка и валидация строк на backend:
  - пустое имя -> пропуск
  - `price <= 0` -> пропуск
  - `гр -> г`, поддерживаемые единицы: `кг`, `г`, `л`, `мл`
  - дубли `name_in_price` внутри одного прайса -> сохраняется минимальная цена
  - секционные строки (типа заголовков категорий) не сохраняются
- Факт загрузки хранится в БД (таблица `prices`, обновление счетчиков по поставщику).

## 2) Заказ

Назначение: ввести текст заказа и безопасно запустить сопоставление.

- Шаг 1 — `Проверить ввод` (`POST /api/order/parse`):
  - очистка строк
  - парсинг в структуру словаря: `name`, `quantity`, `unit`
  - показ разобранных и неразобранных строк
- Шаг 2 — `Сопоставить` (`POST /api/match`):
  - отправка подготовленных данных в backend
  - длительная операция с защитой от зависания на фронте (таймаут запроса)

## 3) Результат

Назначение: показать распределение, суммы и выгрузить Excel.

- Таблица результатов:
  - строки позиций
  - количества по поставщикам
  - суммы по строкам
  - строка `Итого`
- Показ:
  - `not found` позиции (подсветка + отдельный блок)
  - комментарий по строке (выбранный вариант и альтернативы)
- Экспорт: `POST /api/export` -> `result.xlsx`

## Как работает сопоставление (LLM + fallback)

Пайплайн в backend (`match_service`):

1. Парсинг заказа (`order_parser`) в структурированные позиции.
2. Формирование payload:
   - `order_items`
   - список поставщиков
   - строки прайсов по поставщикам
3. Попытка сопоставления через YandexGPT:
   - ответ должен быть валидным JSON
   - есть повторная попытка/repair при битом формате
4. Если LLM недоступна или JSON невалиден:
   - включается `fallback` без ИИ (не валим весь расчет)

### Fallback без ИИ

Если по позиции нет матчей от LLM, backend ищет кандидатов по БД:

- нормализация названий (lowercase, `ё->е`, чистка скобок/хвостов/пробелов)
- фильтр совместимости единиц:
  - масса: `кг/г`
  - объем: `л/мл`
- расчет score:
  - `1.0` за точное совпадение
  - `0.95` за вхождение подстроки
  - иначе score по пересечению токенов (Jaccard)
- порог принятия кандидата: ненулевой/достаточный score (в текущей реализации `>= 0.6`)
- выбор лучшего кандидата у поставщика:
  - выше score
  - при равном score — ниже цена

Далее:
- формируется распределение количества и сумм по поставщикам
- формируется комментарий:
  - выбранный товар
  - альтернативы по поставщикам с релевантным ненулевым score

## Что сохраняется в БД

- Поставщики (`suppliers`)
- Прайсовые позиции (`prices`) после нормализации/валидации
- Технические настройки (`settings`)

История сопоставлений и персистентный словарь соответствий в MVP не ведутся.

## Ключевые файлы

- Backend:
  - `backend/app/api/routes.py`
  - `backend/app/services/match_service.py`
  - `backend/app/services/price_import_service.py`
  - `backend/app/services/export_service.py`
  - `backend/app/parsers/order_parser.py`
- Frontend:
  - `frontend/src/App.tsx`
  - `frontend/src/pages/PricesPage.tsx`
  - `frontend/src/pages/OrderPage.tsx`
  - `frontend/src/pages/ResultPage.tsx`
  - `frontend/src/api.ts`

## Локальный запуск

Backend:

```bash
cd backend
py -m uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm run dev
```

## Деплой (второй проект на VPS)

```bash
cd /opt/tutuorders
git pull

cd /opt/tutuorders/backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart tutuorders-backend

cd /opt/tutuorders/frontend
npm ci
npm run build

sudo nginx -t
sudo systemctl reload nginx
```
