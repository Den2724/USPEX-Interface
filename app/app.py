import datetime as dt
import queue
import threading
import time

import pandas as pd
import streamlit as st

from app import logic


THEMES = [
    {"name": "Ocean", "primary": "#2E86AB", "bg": "#F1F7FB", "text": "#0B1F2A"},
    {"name": "Forest", "primary": "#2D6A4F", "bg": "#F4FBF7", "text": "#0E241B"},
    {"name": "Sunset", "primary": "#E76F51", "bg": "#FFF3EC", "text": "#3A1E16"},
]


def apply_theme(primary: str, bg: str, text: str) -> None:
    css = f"""
    <style>
    .stApp {{
        background: {bg};
        color: {text};
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
    st.session_state.setdefault("custom_theme", {"primary": "#445566", "bg": "#F7F7F2", "text": "#1E1E1E"})


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


def pick_theme() -> None:
    cols = st.columns(len(THEMES) + 1)
    for idx, theme in enumerate(THEMES):
        if cols[idx].button("■", key=f"theme_{theme['name']}", help=theme["name"]):
            st.session_state.theme = theme
    if cols[-1].button("Custom", key="theme_custom"):
        st.session_state.theme = "custom"

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
        apply_theme(
            st.session_state.custom_theme["primary"],
            st.session_state.custom_theme["bg"],
            st.session_state.custom_theme["text"],
        )
    else:
        apply_theme(
            st.session_state.theme["primary"],
            st.session_state.theme["bg"],
            st.session_state.theme["text"],
        )


def run_selected_mode(
    mode: str,
    elements_text: str,
    counts_text: str,
    ratios_text: str,
    min_at_text: str,
    max_at_text: str,
) -> str:
    elements = logic.parse_elements(elements_text)
    if mode == "Fixed composition":
        counts = logic.parse_int_list(counts_text)
        return logic.build_input_fixed(elements, counts)
    if mode == "Single block":
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

    st.markdown("## USPEX runner")
    pick_theme()

    st.markdown("### Paths")
    col1, col2 = st.columns(2)
    exe_path = col1.text_input("Path to uspex.exe", value=logic.DEFAULT_USPEX_EXE)
    workdir = col2.text_input("Workdir", value="")

    st.markdown("### Mode")
    mode = st.radio(
        "Input mode",
        ["Fixed composition", "Single block", "Variable composition"],
        horizontal=True,
    )

    elements_text = st.text_input("Elements (space or comma separated)", value="Si O")

    counts_text = ""
    ratios_text = ""
    min_at_text = "8"
    max_at_text = "18"

    if mode == "Fixed composition":
        counts_text = st.text_input("Counts per element", value="6 12")
    elif mode == "Single block":
        ratios_text = st.text_input("Ratios (integers)", value="1 2")
        min_at_text = st.text_input("minAt", value="8")
        max_at_text = st.text_input("maxAt", value="18")
    else:
        min_at_text = st.text_input("minAt", value="8")
        max_at_text = st.text_input("maxAt", value="18")

    preview = st.empty()
    try:
        preview_text = run_selected_mode(
            mode,
            elements_text,
            counts_text,
            ratios_text,
            min_at_text,
            max_at_text,
        )
    except Exception as exc:
        preview_text = f"(input error: {exc})"

    preview.text_area("INPUT.txt preview", preview_text, height=200)

    st.markdown("### Run")
    run_col, stop_col = st.columns(2)
    run_clicked = run_col.button("Run", disabled=st.session_state.running)
    stop_clicked = stop_col.button("Stop", disabled=not st.session_state.running)

    if run_clicked:
        st.session_state.error = ""
        try:
            input_text = run_selected_mode(
                mode,
                elements_text,
                counts_text,
                ratios_text,
                min_at_text,
                max_at_text,
            )
            logic.write_input_file(workdir, input_text)
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
        except Exception as exc:
            st.session_state.error = str(exc)

    if stop_clicked and st.session_state.proc is not None:
        try:
            st.session_state.proc.terminate()
        except Exception:
            pass

    # Drain queue
    if st.session_state.running:
        while True:
            try:
                kind, payload = st.session_state.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                st.session_state.log_lines.append(payload)
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

    status = st.session_state.status
    st.markdown("### Status")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Generation": status.get("generation"),
                    "Stage": status.get("stage"),
                    "Done steps": status.get("done_steps"),
                    "Total steps": status.get("total_steps"),
                    "Gen size": status.get("gen_size"),
                }
            ]
        ),
        use_container_width=True,
    )

    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        st.line_chart(df.set_index("time")[["done", "total"]])

    st.markdown("### Log")
    st.text_area(
        "USPEX log",
        value="\n".join(st.session_state.log_lines[-500:]),
        height=240,
    )

    if st.session_state.running:
        time.sleep(0.5)
        st.experimental_rerun()


if __name__ == "__main__":
    main()
