# USPEX Runner — Change Log

Формат каждой записи:

* **Дата** — когда внесено
* **Категория** — одна из трёх:

  * `Логика кода` — серверная логика Python/Flask, алгоритмы
  * `Интерфейс` — HTML / CSS / JS (фронтенд)
  * `Работа с ОС` — Tauri/Rust, установщик, процессы, файловая система

\---

## 2026-04-24

\---

\---

### Работа с ОС — Иконки AppImage: генерация PNG

Tauri 2 требует PNG-иконки. Старый ICO был 1×1 пиксель.

* `src-tauri/icons/32x32.png`, `128x128.png`, `icon.png` — сгенерированы через Pillow (синий квадрат #2E86AB с рамкой)
* `src-tauri/tauri.conf.json` — добавлен явный массив `"icon": \["icons/32x32.png", "icons/128x128.png", "icons/icon.png"]`

\---

### Интерфейс — Поле пути к STMng в Paths

* `webapp/templates/index.html` — в grid `.grid.two` в секции Paths добавлен `<input id="stmng\_exe\_path">` и `<div id="stmng\_status">`
* `webapp/static/app.js` — добавлен ключ `path\_stmng` в i18n всех 5 языков (RU/EN/ZH/FA/HI)
* `webapp/static/app.js` — гидрация: `setValue("stmng\_exe\_path", s.stmng\_path || "")`
* `webapp/static/app.js` — `saveSettings` и `queuePathAutoSave` дополнены полем `stmng\_exe\_path`
* `webapp/static/app.js` — добавлен `addEventListener("input", queuePathAutoSave)` на `stmng\_exe\_path`

\---

## 2026-04-25

### Интерфейс — Единый флаг Advanced settings для всех режимов

Три отдельных чекбокса `adv\_toggle\_fixed/single/variable` заменены одним общим.

* `webapp/templates/index.html` — удалены `<label class="inline"><input id="adv\_toggle\_fixed/single/variable">` из `.mode-item`; добавлен `<label class="inline adv-toggle-global"><input id="adv\_toggle">` между `.mode-fields` и `#advanced\_block`
* `webapp/static/app.js` — `readCurrentFormIntoModeCache()`: `adv\_toggle\_${mode}` → `"adv\_toggle"`
* `webapp/static/app.js` — `writeModeCacheToForm()`: цикл по MODES заменён на одно присваивание `advCb.checked = !!modeCache\[mode].advanced\_enabled`
* `webapp/static/app.js` — `updateModeVisibility()`: добавлена синхронизация чекбокса при смене режима
* `webapp/static/app.js` — цикл `for (const m of MODES)` с тремя listener'ами заменён одним listener'ом на `"adv\_toggle"`
* `webapp/static/styles.css` — удалены стили `.mode-item .inline`; добавлены `.adv-toggle-global` и `.adv-toggle-global input\[type="checkbox"]`; `min-height` у `.mode-item` уменьшен с 108px до 56px

\---

### Интерфейс — Модальное окно подтверждения перед запуском Run

* `webapp/templates/index.html` — добавлена модалка `#run\_confirm\_modal` с `<pre id="run\_confirm\_preview">`, строкой workdir `<code id="run\_confirm\_workdir">` и кнопками «Запустить» / «Отмена»
* `webapp/static/app.js` — обработчик `run\_btn` теперь вызывает `openRunConfirmModal()` вместо прямого вызова `/api/run`; кнопка `run\_confirm\_ok\_btn` вызывает `/api/run`; клик на фон и `run\_confirm\_close\_btn` закрывают без запуска
* `webapp/static/app.js` — добавлены ключи `run\_confirm\_title`, `run\_confirm\_proceed`, `run\_cancel` в i18n всех 5 языков
* `webapp/static/styles.css` — добавлен `.run-confirm-preview` (max-height 55vh, overflow-y auto) и `.run-confirm-workdir`

\---

### Интерфейс — Кликабельный эмодзи 🏃 в заголовке

* `webapp/templates/index.html` — эмодзи в `<h1>` обёрнут в `<span id="hero\_run\_emoji" style="cursor:pointer;">`
* `webapp/static/app.js` — добавлен listener: клик на `hero\_run\_emoji` вызывает `run\_btn.click()`

\---

### Интерфейс — File Browser перемещён после Paths; root = workdir

* `webapp/templates/index.html` — секция `#file\_browser\_panel` перемещена с конца страницы на позицию сразу после секции Paths
* `webapp/templates/index.html` — удалено отдельное поле `browser\_root`; браузер теперь использует `workdir` как корень
* `webapp/static/app.js` — добавлена функция `browserRoot()` → `document.getElementById("workdir").value.trim()`
* `webapp/static/app.js` — `loadBrowser()` использует `browserRoot()` вместо `browser\_root` input
* `webapp/static/app.js` — инициализация `browserState` в `refreshState` убирает `setValue("browser\_root", ...)`

\---

### Логика кода — Default workdir: папка projects

* `webapp/server.py` — добавлена функция `\_default\_workdir()`: создаёт `\~/.local/share/uspex-runner/projects/` при первом запуске (`os.makedirs(primary, exist\_ok=True)`) и возвращает этот путь как рабочую папку по умолчанию
* `webapp/server.py` — в `\_apply\_loaded\_config` изменено: `STATE.workdir = str(config.get("workdir") or \_default\_workdir())`
* `install.sh` — добавлена строка `mkdir -p "$INSTALL\_DIR/projects"` в `install\_backend()`

\---

### Интерфейс — Кнопка ＋ создания папки в File Browser

* `webapp/templates/index.html` — добавлена `<button id="browser\_mkdir\_btn" class="browser-mkdir-btn">＋</button>` в панели инструментов браузера
* `webapp/static/app.js` — listener на `browser\_mkdir\_btn`: `prompt(tr("mkdir\_prompt"))` → `api("/api/browser/mkdir", ...)` → `loadBrowser()`
* `webapp/static/app.js` — добавлены ключи `mkdir\_prompt`, `ctx\_rename`, `rename\_prompt` в i18n всех 5 языков
* `webapp/static/styles.css` — добавлены `.browser-mkdir-btn` (цвет `var(--accent)`, прозрачный фон) и состояние `:hover`

\---

### Логика кода — API эндпоинты mkdir и rename для File Browser

* `webapp/server.py` — добавлен `POST /api/browser/mkdir`: принимает `root`, `current`, `name`; валидирует через `\_is\_within\_root`; создаёт директорию через `os.makedirs`
* `webapp/server.py` — добавлен `POST /api/browser/rename`: принимает `root`, `path`, `new\_name`; валидирует через `\_is\_within\_root`; переименовывает через `os.rename`

\---

### Интерфейс — Контекстное меню «Переименовать» на папках

* `webapp/templates/index.html` — добавлен `<div id="browser\_ctx\_menu" class="ctx-menu">` с кнопкой `browser\_ctx\_rename`
* `webapp/static/app.js` — `renderBrowserList`: добавлен `row.dataset.path = d.path` на каждый `.browser-item`
* `webapp/static/app.js` — `contextmenu` listener на `#browser\_dirs`: показывает меню в позиции курсора, сохраняет путь в `ctxTargetPath`
* `webapp/static/app.js` — listener на `browser\_ctx\_rename`: `prompt(tr("rename\_prompt"))` → `api("/api/browser/rename", ...)` → `loadBrowser()`
* `webapp/static/styles.css` — добавлены `.ctx-menu` и `.ctx-item` (position: fixed, box-shadow, hover)

\---

### Интерфейс — Редактируемое поле Current folder + Enter

* `webapp/templates/index.html` — атрибут `readonly` удалён с `<input id="browser\_current">`
* `webapp/static/app.js` — добавлена функция `browserOpenTyped()`: берёт значение из `browser\_current`, вызывает `loadBrowser(typed || browserRoot())`
* `webapp/static/app.js` — listener `keydown` на `browser\_current`: при `Enter` вызывает `browserOpenTyped()`
* `webapp/static/app.js` — listener `browser\_open` обновлён: вызывает `browserOpenTyped()`

\---

### Интерфейс — Кнопка сворачивания/разворачивания File Browser

* `webapp/templates/index.html` — заголовок секции обёрнут в `<div class="section-head">`; добавлена `<button id="browser\_toggle" class="icon-toggle">▾</button>`; содержимое секции обёрнуто в `<div id="browser\_wrap">`
* `webapp/static/app.js` — listener на `browser\_toggle`: `classList.toggle("collapsed")` на `#browser\_wrap`, смена текста `▾`/`▸`

\---

### Интерфейс — Переупорядочивание кнопок File Browser

Порядок кнопок изменён: 🏠 Root → ⬆️ .. → Open → ＋

* `webapp/templates/index.html` — изменён порядок `<button>` элементов в `.browser-toolbar-btns`

\---

### Интерфейс — Кнопка сворачивания/разворачивания раздела Mode

* `webapp/templates/index.html` — заголовок секции Mode обёрнут в `<div class="section-head">`; добавлена `<button id="mode\_toggle" class="icon-toggle">▾</button>`; содержимое секции обёрнуто в `<div id="mode\_wrap">`
* `webapp/static/styles.css` — добавлено правило `#mode\_wrap.collapsed { display: none; }`
* `webapp/static/app.js` — listener на `mode\_toggle`: `classList.toggle("collapsed")` на `#mode\_wrap`, смена текста `▾`/`▸`

### Интерфейс — Исправление кнопки сворачивания File Browser

* `webapp/static/styles.css` — добавлено отсутствующее правило `#browser\_wrap.collapsed { display: none; }` (кнопка существовала, но CSS-правило не было прописано)

\---

## 2026-04-24 — v0.2.0

### Работа с ОС — Автоматический выбор свободного порта

Релизная сборка больше не привязана к порту 8501.

* `run\_backend.py` — полностью переписан: функция `find\_free\_port(8501–8600)` ищет свободный порт через `socket.bind()`; `write\_port\_file(port)` записывает результат в `$INSTALL\_DIR/.port`; `FLASK\_PORT` env-переменная по-прежнему позволяет зафиксировать порт для dev-режима (8502)
* `src-tauri/src/main.rs` — добавлена функция `read\_backend\_port(timeout)`: читает `.port` файл и проверяет TCP-подключение; `create\_main\_window` принимает `port: u16` как параметр; release-блок: запускает backend → ждёт порт → создаёт окно; debug-блок: создаёт окно на порту 8502 без запуска backend из Rust

\---

### Работа с ОС — Переменная USPEX\_INSTALL\_DIR

Единая точка настройки пути установки для всех компонентов.

* `src-tauri/src/main.rs` — добавлена функция `install\_dir()`: читает `USPEX\_INSTALL\_DIR` env, fallback `\~/.local/share/uspex-runner`; `start\_backend()` передаёт `USPEX\_INSTALL\_DIR` дочернему процессу через `cmd.env()`
* `run\_backend.py` — `write\_port\_file()` читает `USPEX\_INSTALL\_DIR` с тем же fallback
* `webapp/server.py` — `\_default\_workdir()` читает `USPEX\_INSTALL\_DIR` для пути к папке `projects/`
* `install.sh` — launcher `\~/.local/bin/uspex-runner` устанавливает `export USPEX\_INSTALL\_DIR="$INSTALL\_DIR"` перед запуском AppImage

\---

### Работа с ОС — Установщик v0.2.0: произвольный путь установки

* `install.sh` — полностью переписан: запрашивает путь установки (default `$HOME/.local/share/uspex-runner`); STMng извлекается в `$INSTALL\_DIR/stmng/`; добавлена функция `install\_uspex\_binary()` — копирует `./uspex` или `./uspex.exe` в `$INSTALL\_DIR/uspex`; `configure\_defaults()` прописывает `exe\_path` и `stmng\_exe\_path` в `\~/.config/USPEX Runner/config.json`; создаётся папка `$INSTALL\_DIR/projects/`
* `src-tauri/tauri.conf.json` — версия поднята до `"0.2.0"`

\---

### Работа с ОС — build\_release.sh: USPEX binary + zip-архив

* `build\_release.sh` — добавлено копирование `./uspex` (или `./uspex.exe`) в `releases/v$VERSION/`; добавлено создание zip-архива `USPEX\_Runner\_$VERSION.zip` из содержимого `releases/v$VERSION/` через `zip -r`

