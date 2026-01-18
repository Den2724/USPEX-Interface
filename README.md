# USPEX Streamlit GUI

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
