import datetime as dt
import json
import os
import queue
import threading
import time
from typing import Any

import streamlit as st

from app import logic


THEMES = [
    {"name": "Ocean", "primary": "#2E86AB", "bg": "#F1F7FB", "text": "#0B1F2A"},
    {"name": "Forest", "primary": "#2D6A4F", "bg": "#F4FBF7", "text": "#0E241B"},
    {"name": "Sunset", "primary": "#E76F51", "bg": "#FFF3EC", "text": "#3A1E16"},
    {"name": "Violet Pulse", "primary": "#7B2CBF", "bg": "#F7F0FF", "text": "#2B103B"},
    {"name": "Deep Blue", "primary": "#1D4ED8", "bg": "#EFF6FF", "text": "#0B1A4A"},
    {"name": "Noir", "primary": "#111827", "bg": "#F2F2F2", "text": "#0F0F0F"},
    {"name": "White Linen", "primary": "#E5E7EB", "bg": "#FFFFFF", "text": "#111827"},
    {"name": "Pink Bloom", "primary": "#EC4899", "bg": "#FFF1F8", "text": "#4A0C2C"},
]

CONFIG_PATH = "config.json"
LOG_MAX_LINES = 1500

LANGUAGES = {
    "ru": {"name": "Русский", "flag": "🇷🇺"},
    "en": {"name": "English", "flag": "🇬🇧"},
    "zh": {"name": "中文", "flag": "🇨🇳"},
}

TEXT = {
    "title": {"ru": "USPEX runner 🏃", "en": "USPEX runner 🏃", "zh": "USPEX runner 🏃"},
    "theme": {"ru": "Тема", "en": "Theme", "zh": "主题"},
    "language": {"ru": "Язык", "en": "Language", "zh": "语言"},
    "paths": {"ru": "Пути", "en": "Paths", "zh": "路径"},
    "exe_path": {"ru": "Путь к uspex.exe", "en": "Path to uspex.exe", "zh": "uspex.exe 路径"},
    "workdir": {"ru": "Рабочая папка", "en": "Workdir", "zh": "工作目录"},
    "browse_exe": {"ru": "Выбрать exe", "en": "Browse exe", "zh": "选择 exe"},
    "browse_folder": {"ru": "Выбрать папку", "en": "Browse folder", "zh": "选择文件夹"},
    "mode": {"ru": "Режим", "en": "Mode", "zh": "模式"},
    "elements": {"ru": "Элементы (через пробел или запятую)", "en": "Elements (space or comma separated)", "zh": "元素（空格或逗号分隔）"},
    "counts": {"ru": "Число атомов по элементам", "en": "Counts per element", "zh": "每种元素原子数"},
    "ratios": {"ru": "Соотношение (целые числа)", "en": "Ratios (integers)", "zh": "比例（整数）"},
    "min_at": {"ru": "minAt", "en": "minAt", "zh": "minAt"},
    "max_at": {"ru": "maxAt", "en": "maxAt", "zh": "maxAt"},
    "preview": {"ru": "Предпросмотр INPUT.txt", "en": "INPUT.txt preview", "zh": "INPUT.txt 预览"},
    "run": {"ru": "Запустить", "en": "Run", "zh": "运行"},
    "stop": {"ru": "Остановить", "en": "Stop", "zh": "停止"},
    "status": {"ru": "Статус", "en": "Status", "zh": "状态"},
    "log": {"ru": "Лог", "en": "Log", "zh": "日志"},
    "preview_source": {
        "ru": "Определяющим является текст в данном окне.",
        "en": "The preview text is the source of truth.",
        "zh": "以此处预览文本为准。",
    },
    "reset_preview": {
        "ru": "Вернуть согласно параметрам",
        "en": "Reset to parameters",
        "zh": "恢复为参数生成",
    },
    "go_latest": {
        "ru": "К актуальным изменениям",
        "en": "Go to latest",
        "zh": "跳到最新",
    },
}

MODE_LABELS = {
    "fixed": {"ru": "Знаю состав", "en": "Fixed composition", "zh": "固定组成"},
    "single": {"ru": "Знаю соотношение", "en": "Single block", "zh": "已知比例"},
    "variable": {"ru": "Знаю элементы", "en": "Variable composition", "zh": "已知元素"},
}

MODE_HELP = {
    "fixed": {
        "ru": "Когда вы точно знаете состав кристаллической ячейки. "
              "Генерируются структуры с фиксированным числом атомов в ячейке.",
        "en": "Use when you know the exact crystal composition. "
              "Generates structures with a fixed number of atoms in the cell.",
        "zh": "当你确定晶胞的准确组成时使用。生成固定原子数的结构。",
    },
    "single": {
        "ru": "Когда известно соотношение элементов, но неизвестно число атомов. "
              "USPEX варьирует число атомов в пределах min/max.",
        "en": "Use when the element ratio is known but the atom count is not. "
              "USPEX varies atoms within min/max.",
        "zh": "当已知元素比例但不确定原子数时使用。USPEX 在 min/max 范围内调整原子数。",
    },
    "variable": {
        "ru": "Когда известны элементы, но неизвестны составы. "
              "USPEX перебирает разные составы и структуры в пределах minAt-maxAt.",
        "en": "Use when only the elements are known. "
              "USPEX explores compositions and structures within minAt-maxAt.",
        "zh": "当只知道元素但不确定组成时使用。USPEX 在 minAt-maxAt 范围内探索组成与结构。",
    },
}


def apply_theme(primary: str, bg: str, text: str, task_text: str) -> None:
    css = f"""
    <style>
    .stApp {{
        background: {bg};
        color: {text};
    }}
    .stMarkdown, .stText, p, span {{
        color: {text};
    }}
    label, .stTextInput label, .stTextArea label, .stSelectbox label, .stRadio label {{
        color: {task_text};
    }}
    .stButton > button {{
        border-radius: 6px;
        border: 1px solid {primary};
    }}
    .stButton > button:focus {{
        outline-color: {primary};
    }}
    .stProgress > div > div > div > div {{
        background-color: {primary};
    }}
    a, a:visited {{ color: {primary}; }}
    [data-testid="baseButton-secondary"] {{
        padding: 0;
    }}
    [data-testid="baseButton-secondary"] > button {{
        width: 32px;
        height: 32px;
        padding: 0;
        border-radius: 6px;
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        outline: none !important;
    }}
    [data-testid="baseButton-secondary"] > button:hover,
    [data-testid="baseButton-secondary"] > button:active,
    [data-testid="baseButton-secondary"] > button:focus {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }}
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="column"]) {{
        margin-top: 0;
        padding-top: 0;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def init_state() -> None:
    st.session_state.setdefault("proc", None)
    st.session_state.setdefault("queue", queue.Queue())
    st.session_state.setdefault("thread", None)
    st.session_state.setdefault("monitor", logic.UspexMonitor())
    st.session_state.setdefault("log_lines", [])
    st.session_state.setdefault("status", logic.UspexMonitor().to_dict())
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("running", False)
    st.session_state.setdefault("error", "")
    st.session_state.setdefault("theme", THEMES[0])
    st.session_state.setdefault(
        "custom_theme",
        {"primary": "#445566", "bg": "#F7F7F2", "text": "#1E1E1E", "task_text": "#1E1E1E"},
    )
    st.session_state.setdefault("language", "ru")
    st.session_state.setdefault("input_preview", "")
    st.session_state.setdefault("preview_dirty", False)
    st.session_state.setdefault("last_expected", "")


def load_config() -> dict:
    if not os.path.isfile(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=True, indent=2)
    except Exception:
        pass


def t(key: str) -> str:
    lang = st.session_state.get("language", "ru")
    return TEXT.get(key, {}).get(lang, TEXT.get(key, {}).get("en", key))


def pick_language() -> None:
    st.markdown(f"### {t('language')}")
    codes = list(LANGUAGES.keys())
    cols = st.columns(len(codes))
    for i, code in enumerate(codes):
        label = LANGUAGES[code]["flag"]
        if cols[i].button(label, key=f"lang_{code}", help=LANGUAGES[code]["name"], type="secondary"):
            st.session_state.language = code


def reader_loop(proc, q: queue.Queue) -> None:
    try:
        for line in proc.stdout:
            q.put(("line", line.rstrip("\n")))
    except Exception as exc:
        q.put(("err", str(exc)))
    finally:
        code = None
        try:
            code = proc.wait(timeout=1)
        except Exception:
            pass
        q.put(("exit", code))


def pick_theme(title: str) -> Any:
    st.markdown(f"### {title}")
    theme_names = [t["name"] for t in THEMES] + ["Custom"]
    theme_icons = {
        "Ocean": "🟦",
        "Forest": "🟩",
        "Sunset": "🟧",
        "Violet Pulse": "🟪",
        "Deep Blue": "🟦",
        "Noir": "⬛",
        "White Linen": "⬜",
        "Pink Bloom": "🩷",
        "Custom": "🎨",
    }
    cols = st.columns(len(theme_names))
    for i, name in enumerate(theme_names):
        label = theme_icons.get(name, "⬜")
        if cols[i].button(label, key=f"theme_btn_{name}", help=name, type="secondary"):
            if name == "Custom":
                st.session_state.theme = "custom"
            else:
                st.session_state.theme = next(t for t in THEMES if t["name"] == name)

    if st.session_state.theme == "custom":
        st.session_state.custom_theme["primary"] = st.color_picker(
            "Primary", st.session_state.custom_theme["primary"]
        )
        st.session_state.custom_theme["bg"] = st.color_picker(
            "Background", st.session_state.custom_theme["bg"]
        )
        st.session_state.custom_theme["text"] = st.color_picker(
            "Text", st.session_state.custom_theme["text"]
        )
        st.session_state.custom_theme["task_text"] = st.color_picker(
            "Task text", st.session_state.custom_theme["task_text"]
        )
        apply_theme(
            st.session_state.custom_theme["primary"],
            st.session_state.custom_theme["bg"],
            st.session_state.custom_theme["text"],
            st.session_state.custom_theme["task_text"],
        )
    else:
        theme = st.session_state.theme
        apply_theme(theme["primary"], theme["bg"], theme["text"], theme["text"])
    return st.session_state.theme


def pick_file_dialog(title: str, filetypes: list[tuple[str, str]]) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return path or ""


def pick_dir_dialog(title: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    path = filedialog.askdirectory(title=title)
    root.destroy()
    return path or ""


def on_pick_exe() -> None:
    picked = pick_file_dialog("Select uspex.exe", [("Executable", "*.exe"), ("All files", "*.*")])
    if picked:
        st.session_state.exe_path = picked


def on_pick_workdir() -> None:
    picked = pick_dir_dialog("Select workdir")
    if picked:
        st.session_state.workdir = picked




def run_selected_mode(
    mode: str,
    elements_text: str,
    counts_text: str,
    ratios_text: str,
    min_at_text: str,
    max_at_text: str,
) -> str:
    elements = logic.parse_elements(elements_text)
    if mode == "fixed":
        counts = logic.parse_int_list(counts_text)
        return logic.build_input_fixed(elements, counts)
    if mode == "single":
        ratios = logic.parse_int_list(ratios_text)
        min_at = int(min_at_text)
        max_at = int(max_at_text)
        return logic.build_input_single(elements, ratios, min_at, max_at)
    min_at = int(min_at_text)
    max_at = int(max_at_text)
    return logic.build_input_variable(elements, min_at, max_at)


def main() -> None:
    init_state()
    st.set_page_config(page_title="USPEX Streamlit GUI", layout="wide")
    st.set_option("client.showErrorDetails", False)

    st.markdown(
        """
        <style>
        .sticky-panel {
            position: sticky;
            top: 0;
            z-index: 999;
            padding: 8px 0 6px 0;
            backdrop-filter: blur(8px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    config = load_config()
    if config:
        if "exe_path" not in st.session_state:
            st.session_state.exe_path = config.get("exe_path", logic.DEFAULT_USPEX_EXE)
        if "workdir" not in st.session_state:
            st.session_state.workdir = config.get("workdir", "")
        if "elements_text" not in st.session_state:
            st.session_state.elements_text = config.get("elements_text", "Si O")
        if "counts_text" not in st.session_state:
            st.session_state.counts_text = config.get("counts_text", "6 12")
        if "ratios_text" not in st.session_state:
            st.session_state.ratios_text = config.get("ratios_text", "1 2")
        if "min_at_text" not in st.session_state:
            st.session_state.min_at_text = config.get("min_at_text", "8")
        if "max_at_text" not in st.session_state:
            st.session_state.max_at_text = config.get("max_at_text", "18")
        if "mode" not in st.session_state:
            saved_mode = config.get("mode", "fixed")
            legacy = {
                "Fixed composition": "fixed",
                "Single block": "single",
                "Variable composition": "variable",
            }
            st.session_state.mode = legacy.get(saved_mode, saved_mode)
        if "language" not in st.session_state:
            st.session_state.language = config.get("language", "ru")
        saved_theme = config.get("theme")
        if saved_theme == "custom":
            st.session_state.theme = "custom"
            st.session_state.custom_theme.update(config.get("custom_theme", {}))
        elif saved_theme and st.session_state.theme != "custom":
            for theme in THEMES:
                if theme["name"] == saved_theme:
                    st.session_state.theme = theme
                    break

    lang_col, theme_col, _ = st.columns([1, 2, 3])
    with lang_col:
        pick_language()
    with theme_col:
        active_theme = pick_theme(t("theme"))

    st.markdown(f"## {t('title')}")

    st.markdown(f"### {t('paths')}")
    col1, col2 = st.columns([4, 1])
    exe_path = col1.text_input(
        t("exe_path"),
        value=st.session_state.get("exe_path", logic.DEFAULT_USPEX_EXE),
        key="exe_path",
    )
    col2.button(t("browse_exe"), on_click=on_pick_exe)

    col3, col4 = st.columns([4, 1])
    workdir = col3.text_input(t("workdir"), value=st.session_state.get("workdir", ""), key="workdir")
    col4.button(t("browse_folder"), on_click=on_pick_workdir)

    st.markdown(f"### {t('mode')}")
    mode_labels = [MODE_LABELS[m].get(st.session_state.language, MODE_LABELS[m]["en"]) for m in ["fixed", "single", "variable"]]
    cols = st.columns(3)
    for i, m in enumerate(["fixed", "single", "variable"]):
        label = mode_labels[i]
        if st.session_state.mode == m:
            label = f"✅ {label}"
        if cols[i].button(label, key=f"mode_btn_{m}", help=MODE_HELP[m].get(st.session_state.language, MODE_HELP[m]["en"])):
            st.session_state.mode = m
    mode = st.session_state.mode

    elements_text = st.text_input(
        t("elements"),
        value=st.session_state.get("elements_text", "Si O"),
        key="elements_text",
    )

    counts_text = ""
    ratios_text = ""
    min_at_text = "8"
    max_at_text = "18"

    if mode == "fixed":
        counts_text = st.text_input(
            t("counts"),
            value=st.session_state.get("counts_text", "6 12"),
            key="counts_text",
        )
    elif mode == "single":
        ratios_text = st.text_input(
            t("ratios"),
            value=st.session_state.get("ratios_text", "1 2"),
            key="ratios_text",
        )
        min_at_text = st.text_input(
            t("min_at"),
            value=st.session_state.get("min_at_text", "8"),
            key="min_at_text",
        )
        max_at_text = st.text_input(
            t("max_at"),
            value=st.session_state.get("max_at_text", "18"),
            key="max_at_text",
        )
    else:
        min_at_text = st.text_input(
            t("min_at"),
            value=st.session_state.get("min_at_text", "8"),
            key="min_at_text",
        )
        max_at_text = st.text_input(
            t("max_at"),
            value=st.session_state.get("max_at_text", "18"),
            key="max_at_text",
        )

    try:
        expected_text = run_selected_mode(
            mode,
            elements_text,
            counts_text,
            ratios_text,
            min_at_text,
            max_at_text,
        )
    except Exception as exc:
        expected_text = f"(input error: {exc})"

    if st.session_state.last_expected != expected_text and not st.session_state.preview_dirty:
        st.session_state.input_preview = expected_text

    st.session_state.preview_dirty = st.session_state.input_preview != expected_text
    st.session_state.last_expected = expected_text

    st.text_area(t("preview"), st.session_state.input_preview, height=200, key="input_preview")

    if st.session_state.preview_dirty:
        st.info(t("preview_source"))
        if st.button(t("reset_preview")):
            st.session_state.input_preview = expected_text
            st.session_state.preview_dirty = False
            st.session_state.last_expected = expected_text

    st.markdown(f"### {t('run')}")
    st.markdown("<div class='sticky-panel'>", unsafe_allow_html=True)
    run_col, stop_col = st.columns([1, 1])
    run_clicked = run_col.button(t("run"), disabled=st.session_state.running, use_container_width=True, type="primary")
    stop_clicked = stop_col.button(t("stop"), disabled=not st.session_state.running, use_container_width=True, type="primary")
    st.markdown("</div>", unsafe_allow_html=True)

    if run_clicked:
        st.session_state.error = ""
        try:
            logic.write_input_file(workdir, st.session_state.input_preview)
            proc = logic.start_uspex_process(exe_path, workdir)
            st.session_state.proc = proc
            st.session_state.queue = queue.Queue()
            st.session_state.monitor = logic.UspexMonitor()
            st.session_state.log_lines = []
            st.session_state.history = []
            st.session_state.running = True
            st.session_state.thread = threading.Thread(
                target=reader_loop, args=(proc, st.session_state.queue), daemon=True
            )
            st.session_state.thread.start()
            save_config(
                {
                    "exe_path": st.session_state.get("exe_path", ""),
                    "workdir": st.session_state.get("workdir", ""),
                    "elements_text": elements_text,
                    "counts_text": counts_text,
                    "ratios_text": ratios_text,
                    "min_at_text": min_at_text,
                    "max_at_text": max_at_text,
                    "mode": mode,
                    "theme": "custom" if active_theme == "custom" else active_theme["name"],
                    "custom_theme": st.session_state.custom_theme,
                    "language": st.session_state.language,
                }
            )
        except Exception as exc:
            st.session_state.error = str(exc)

    if stop_clicked and st.session_state.proc is not None:
        logic.stop_uspex_process(st.session_state.proc)

    # Drain queue
    if st.session_state.running:
        while True:
            try:
                kind, payload = st.session_state.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                st.session_state.log_lines.append(payload)
                if len(st.session_state.log_lines) > LOG_MAX_LINES * 2:
                    st.session_state.log_lines = st.session_state.log_lines[-LOG_MAX_LINES:]
                info = st.session_state.monitor.feed_line(payload)
                if info:
                    st.session_state.status = info
                    st.session_state.history.append(
                        {
                            "time": dt.datetime.now(),
                            "done": info.get("done_steps") or 0,
                            "total": info.get("total_steps") or 0,
                        }
                    )
            elif kind == "err":
                st.session_state.log_lines.append(f"[GUI] Read error: {payload}")
            elif kind == "exit":
                st.session_state.log_lines.append(f"[GUI] USPEX exited (code: {payload})")
                st.session_state.running = False
                st.session_state.proc = None

    if st.session_state.error:
        st.error(st.session_state.error)
        query = st.session_state.error.replace(" ", "+")
        st.markdown(
            f"[Ask Yandex](https://yandex.com/search/?text={query})",
            unsafe_allow_html=True,
        )

    status = st.session_state.status
    st.markdown(f"### {t('status')}")
    st.markdown(
        f"Generation: {status.get('generation') or '—'} | "
        f"Stage: {status.get('stage') or '—'} | "
        f"Done: {status.get('done_steps') or 0} | "
        f"Total: {status.get('total_steps') or 0} | "
        f"Gen size: {status.get('gen_size') or '—'}"
    )

    st.markdown(f"### {t('log')}")
    st.text_area(
        t("log"),
        value="\n".join(st.session_state.log_lines[-LOG_MAX_LINES:]),
        height=240,
    )

    if st.session_state.running:
        time.sleep(0.5)
        st.rerun()


if __name__ == "__main__":
    main()
