# Speed Friending

Веб-приложение для speed-friending мероприятий: ведущий создаёт событие, участники заходят по коду, в каждом раунде система случайно (по возможности без повторов) разбивает всех на пары, показывает вопрос для разговора и таймер. Между раундами — перерыв, в котором участник уже видит следующего партнёра.

Стек: **FastAPI + SQLModel (SQLite в dev / PostgreSQL в prod) + Jinja2-шаблоны с inline-JS**. Realtime через **polling** (WebSocket нет). Деплой: Railway (приложение + Postgres).

---

## Быстрый старт

```bash
pip install -r requirements.txt     # в т.ч. psycopg2-binary для Postgres
cp .env.example .env
uvicorn main:app --reload
```

Страницы: `/` (создать событие), `/join` (вход участника), `/facilitator/login` (вход ведущего).

### Переменные окружения (`config.py`)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` включает CORS/TrustedHost, требует `DATABASE_URL` и `SECRET_KEY` |
| `DATABASE_URL` | `sqlite:///database.db` (только dev) | подключение к БД |
| `TALK_DURATION_MINUTES` | `5` | длительность разговора |
| `BREAK_DURATION_SECONDS` | `60` | длительность перерыва |
| `SECRET_KEY` | dev-заглушка | обязателен в prod |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | TrustedHost и CORS в prod (`*.up.railway.app` допустим) |
| `PHOTO_UPLOAD_DIR` | `static/uploads/photos` | хранилище фото |
| `PHOTO_MAX_SIZE_MB` | `5.0` | лимит фото |

Для отладки: `TALK_DURATION_MINUTES=1`, `BREAK_DURATION_SECONDS=10`.

---

## Структура проекта

```
main.py              # FastAPI app, middleware, static, роутеры, create_all на startup
config.py            # класс Config (env)
db.py                # engine (SQLite/Postgres), create_db_and_tables(), get_session()
dependencies.py      # jinja_env, get_event (по join_code), verify_pin (join_code + ?pin=)
models.py            # SQLModel-таблицы, MINSK_TZ, UTCDateTime
schemas.py           # Pydantic-схемы
validators.py        # валидация title / nickname (5–50 симв.) / join_code / вопросов (5–500, ≤50 шт.)
routers/
  events.py          # публичные: создание, info/state/timer, вопросы, auto_advance
  participants.py    # join, список, фото, my_match, mark_met, страница участника
  facilitator.py     # PIN-защищённые: dashboard, start/next_round, end_event, вопросы, удаление участника
services/
  pairing.py         # make_pairs(): подбор пар
  photo.py           # PhotoService: фото на диске
templates/           # index, join, participant, facilitator_login, facilitator (.html)
static/              # статика; static/uploads/photos — фото
```

Имена модулей важны: код импортирует `db`, `dependencies`, `config`, `models`, `schemas`, `validators`.

---

## Модель данных

- **Event** — `join_code` (unique, 6 симв.), `facilitator_pin` (4 цифры), `status` (`created/running/ended`), `current_round` (0 = не начато), `phase` (`lobby/talk/break/ended`), `phase_ends_at`.
- **Participant** — `event_id`, `nickname` (lower-case, уникален в событии), `email?`, `photo_filename?`, `joined_at`.
- **Round** — `number`, `started_at`, `ends_at` (создаётся при старте фазы talk).
- **Pairing** — `round_number`, `p1_id`, `p2_id` (`NULL` = отдыхает при нечётном числе), `status` (`assigned/met`), `met_at`.
- **PairHistory** — уже встречавшиеся пары `(event_id, a_id, b_id)`, `a_id < b_id`, UNIQUE.
- **Question** — один вопрос на раунд.

### Время

- Все datetime-поля хранятся **в UTC** (тип `UTCDateTime` в `models.py`: в БД naive UTC, наружу aware UTC). Это не зависит от часового пояса сессии БД — на Railway Postgres работает в UTC, а SQLite в dev ведёт себя так же.
- Новое время всегда создаётся как `datetime.now(MINSK_TZ)` (aware), сравнения корректны между зонами.
- Единственный источник правды по таймеру фазы — `event.phase_ends_at`; клиенты должны опираться на `seconds_left` из `/state`, а не на локальные часы.
- Нельзя хранить aware-время в обычных `datetime`-колонках Postgres: оно приводится к зоне сессии и теряет зону — из-за этого раньше таймер показывал 00:00 (сдвиг на 3 часа).

---

## Жизненный цикл события

```
lobby ──start_round──▶ talk (round 1; Pairing раунда 1)
                         │ время вышло (auto_advance) или next_round ведущего
                         ▼
                       break   ← здесь создаются Pairing для раунда N+1; current_round всё ещё N
                         │ перерыв закончился
                         ▼
                       talk (round N+1, current_round = N+1, создаётся Round)
                         ▼ ...
                       ended (end_event)
```

1. Пары раунда N+1 генерируются на переходе **talk → break**; в перерыве `my_match` отдаёт `next_partner_preview`.
2. `current_round` растёт только на **break → talk**.
3. Переход триггерится клиентами (`POST /auto_advance`, срабатывает если `phase_ends_at` прошёл) или ведущим (`POST /next_round`).
4. Переходы выполняются под блокировкой строки события (`SELECT ... FOR UPDATE`, затем повторная проверка `phase`), иначе одновременные вызовы клиентов создают дубли `Round`/`Pairing` и ломают `PairHistory` (UNIQUE).

---

## Подбор пар (`services/pairing.py`)

`make_pairs(session, event_id, participant_ids, round_number) -> list[tuple[int, int | None]]`

1. Из `PairHistory` строится множество уже встречавшихся пар.
2. При нечётном числе участников отдыхает тот, кто отдыхал реже всего (среди равных — случайный); если для него не находится полный набор новых пар, берётся следующий кандидат.
3. Оставшиеся разбиваются **рандомизированным backtracking'ом** в идеальное паросочетание, где нет ни одной уже встречавшейся пары (лимит шагов 20 000).
4. Если такого паросочетания нет (участников мало или раундов слишком много), используется жадный запасной вариант с минимумом повторов.
5. Новые пары записываются в `PairHistory`, повторные — нет.

Замеры на 300 симуляциях: при 10 участниках полный круг из 9 раундов без повторов получается в ~80% случаев, а повторы, если и возникают, — в последних раундах (медиана 8-й). Старая жадная версия давала повтор уже на 4-м раунде. Теоретический максимум без повторов: `n-1` раундов (чётное n) или `n` (нечётное).

---

## API

`{code}` = `join_code` (регистронезависим). PIN-эндпоинты требуют `?pin=XXXX`.

### Страницы
| Метод | Путь |
|---|---|
| GET | `/`, `/join`, `/facilitator/login` |
| GET | `/events/{code}/participant_view?nickname=` |
| GET | `/events/{code}/facilitator` |

### Публичные (`events.py`)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/events` | создать → `join_code`, `facilitator_pin` |
| GET | `/events/{code}/info` | информация + счётчики |
| GET | `/events/{code}/state` | для polling: `status, current_round, phase, seconds_left, participants_count, pairings_count` |
| GET | `/events/{code}/timer` | устаревший: считает по `Round.ends_at`, фазу отдаёт как `running`; использовать `/state` |
| GET | `/events/{code}/current_question` | вопрос раунда (в break — следующего) |
| GET | `/events/{code}/list_questions` | все вопросы |
| POST | `/events/{code}/auto_advance` | продвинуть фазу, если время вышло |

### Участник (`participants.py`)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/events/{code}/join` | `{nickname, email?}` |
| GET | `/events/{code}/participants` | список с фото |
| POST | `/events/{code}/upload_photo?nickname=` | multipart `photo` (jpg/png) |
| GET | `/events/{code}/my_match?nickname=` | `waiting / paired / no_pair / waiting_for_pairing / next_partner_preview / resting / ended` |
| POST | `/events/{code}/mark_met` | `{nickname}`, только в talk |

### Ведущий (`facilitator.py`, все с `?pin=`)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/events/{code}/verify_facilitator` | проверка PIN |
| GET | `/events/{code}/dashboard` | участники, пары текущего раунда, таймер |
| POST | `/events/{code}/start_round` | старт (раунд 1), ≥2 участников |
| POST | `/events/{code}/next_round` | ручной переход talk→break / break→talk (перерыв нельзя пропустить) |
| POST | `/events/{code}/end_event` | завершить |
| POST | `/events/{code}/upload_questions` | `{questions: [...]}`, заменяет все; нельзя при `status=running` |
| DELETE | `/events/{code}/participants/{nickname}` | удалить участника, его пары, историю и фото |

---

## Деплой на Railway

- Сервис приложения: `DATABASE_URL` брать ссылкой на сервис Postgres (`${{Postgres.DATABASE_URL}}`), не хардкодить пароль.
- `ENVIRONMENT=production`, сильный `SECRET_KEY`, `ALLOWED_HOSTS` с доменом приложения.
- Файловая система Railway эфемерна: фото пропадают при деплое. Нужен Volume (смонтировать в `PHOTO_UPLOAD_DIR`) или S3.
- Миграций нет: `create_all` не меняет существующие таблицы. При смене схемы (в т.ч. типа datetime-колонок) старые события нужно удалить или пересоздать таблицы.

---

## Тестирование

Минимальный прогон для проверки пар и переходов (≈10 человек или 10 вкладок/сессий):
1. Создать событие, загрузить вопросы, зайти 10 никнеймами (≥5 символов), выставить короткие `TALK_DURATION_MINUTES=1`, `BREAK_DURATION_SECONDS=10`.
2. `start_round` и прогнать 7–9 раундов.
3. Проверить в БД отсутствие повторов и дублей:

```sql
-- повторяющиеся пары (должно быть пусто, пока раундов ≤ n-1)
SELECT LEAST(p1_id,p2_id) a, GREATEST(p1_id,p2_id) b, count(*)
FROM pairing WHERE p2_id IS NOT NULL
GROUP BY 1,2 HAVING count(*) > 1;

-- дубли пар/раундов (должно быть пусто)
SELECT round_number, count(*) FROM pairing WHERE event_id = :id GROUP BY 1 HAVING count(*) <> :n_participants/2.0;
SELECT number, count(*) FROM round WHERE event_id = :id GROUP BY 1 HAVING count(*) > 1;
```

4. Проверить `/events/{code}/state`: `seconds_left` убывает от ~300 (или выставленного значения), `current_round` не растёт сам.

---

## Известные ограничения / TODO

- Пары: при n участников без повторов гарантированно не более n-1 раундов; backtracking вероятностный — в последних раундах возможны повторы.
- Нет ограничения числа раундов по числу вопросов/уникальных пар.
- `/timer` несогласован с фазами — фронт должен использовать `/state`.
- `next_round` при `phase == "ended"` уходит в ветку старта нового раунда — стоит добавить явный отказ.
- PIN в query string попадает в логи.
- Polling вместо WebSocket/SSE.
- Нет миграций (Alembic).
