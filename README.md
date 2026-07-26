# USPEX Streamlit GUI

## Required binaries (not included in this repository)

This repository contains only the wrapper/GUI code. It does **not** include and will **not** accept commits of:

- `uspex.exe` — the USPEX binary itself
- `STMng-*-setup.exe` — the STMng visualizer installer

Both are distributed under their own license by the USPEX team and must be obtained separately from the official USPEX website: https://uspex-team.org/

Before running or building the installer:

1. Place the USPEX executable as `uspex.exe` in the repository root (or point the app to its actual location via the Paths settings / `config.json`).
2. Place the STMng installer in the repository root, matching the filename referenced in `packaging/installer.iss` (currently `STMng-1.68.3-setup.exe`) — update that filename in `installer.iss` if you have a different STMng version.

## Требуемые бинарники (не входят в репозиторий)

Этот репозиторий содержит только код обёртки/интерфейса. Он **не** включает и **не** принимает в коммиты:

- `uspex.exe` — сам бинарник USPEX
- `STMng-*-setup.exe` — установщик визуализатора STMng

Оба распространяются по собственной лицензии USPEX team и должны быть получены отдельно с официального сайта USPEX: https://uspex-team.org/

Перед запуском или сборкой инсталлятора:

1. Положите исполняемый файл USPEX как `uspex.exe` в корень репозитория (или укажите приложению его фактическое расположение через настройки Paths / `config.json`).
2. Положите установщик STMng в корень репозитория с именем, указанным в `packaging/installer.iss` (сейчас это `STMng-1.68.3-setup.exe`) — при другой версии STMng измените имя файла в `installer.iss`.

## HTML/Flask Version (No Streamlit)

This repository now also includes a non-Streamlit web interface:

- Backend: `webapp/server.py` (Flask API + process management)
- Frontend: `webapp/templates/index.html` + `webapp/static/*`
- Entrypoint: `run_webapp.py`

Run:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run_webapp.py
```

Then open `http://127.0.0.1:8501`.

Notes:

- This mode is intended for local/portable usage without Streamlit.
- STMng/uspex executable integration still requires local Windows paths and binaries.

### Tauri Desktop (Windows)

Run in native desktop window (without browser tabs):

```bash
npm install
npm run tauri:dev
```

Build Windows bundle:

```bash
powershell -ExecutionPolicy Bypass -File packaging/build_tauri_windows.ps1
```

## English

This project wraps `uspex.exe` with a Streamlit interface. You can choose one of three input modes, preview `INPUT.txt`, and run USPEX while streaming logs and progress.

### Run

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Start the app:

```bash
python -m app
```

Or:

```bash
streamlit run app/app.py
```

### Notes

- The original notebook is kept for reference.
- `INPUT.txt` is written into the selected workdir.
- Last-used paths and parameters are saved to `config.json`.

## Русский

Этот проект запускает `uspex.exe` через Streamlit-интерфейс. Доступны три режима ввода, предпросмотр `INPUT.txt`, запуск USPEX и вывод логов и прогресса.

### Запуск

1. Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Запустите приложение:

```bash
python -m app
```

Или:

```bash
streamlit run app/app.py
```

### Примечания

- Оригинальный ноутбук сохранен для справки.
- `INPUT.txt` записывается в выбранную рабочую папку.
- Последние пути и параметры сохраняются в `config.json`.

## 中文

该项目通过 Streamlit 界面启动 `uspex.exe`。提供三种输入模式、`INPUT.txt` 预览，以及 USPEX 运行日志和进度显示。

### 运行

1. 创建虚拟环境并安装依赖：

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. 启动应用：

```bash
python -m app
```

或：

```bash
streamlit run app/app.py
```

### 说明

- 保留原始 notebook 作为参考。
- `INPUT.txt` 写入所选工作目录。
- 最近使用的路径和参数会保存到 `config.json`。
