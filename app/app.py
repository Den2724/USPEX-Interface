import datetime as dt
import json
import math
import os
import queue
import tempfile
import threading
import time
import urllib.parse
from typing import Any

import pandas as pd
import streamlit as st

# Streamlit Cloud may execute app/app.py as module "app", which breaks
# `from app import logic` due to partial module initialization.
if __package__:
    from . import logic
else:
    import logic  # type: ignore
import re
import sys
import subprocess


_CALCFOLD_RE = re.compile(r"^Calcfold_(\d+)_(\d+)$")
STMNG_EXE_PATH = r"C:\Program Files\STMng\STMng.exe"
STMNG_WORKDIR = r"C:\Program Files\STMng"
STMNG_TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "test.stm"))
STMNG_XYZ_TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "xyz_test.stm"))
_COMMENT_RE = re.compile(
    r"Gen\s*=\s*(?P<Gen>[-+]?\d+)\s*,\s*"
    r"generation\s*=\s*(?P<generation>[-+]?\d+)\s*,\s*"
    r"number\s*=\s*(?P<number>[-+]?\d+)\s*,\s*"
    r"energy\s*=\s*(?P<energy>[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)"
)

def render_preview_results_panel() -> None:
    workdir = st.session_state.get("workdir", "").strip()
    data = scan_preview_results(workdir)
    calc_dir = data["calculation_dir"]
    structures = data["structures"]

    st.markdown("### Предв. результаты")

    if not workdir:
        st.warning("Рабочая папка не выбрана.")
        return

    if not os.path.isdir(calc_dir):
        st.warning(f"Папка Calculation не найдена: {calc_dir}")
        return

    c_refresh, _ = st.columns([1, 6])
    if c_refresh.button("Обновить список", key="refresh_preview_btn"):
        st.rerun()

    if not structures:
        st.info("Не найдено ни одной папки Calcfold_N_M внутри Calculation.")
        return

    st.markdown("**Структуры и стадии релаксации (успех = найден output.xyz):**")

    header_n, header_1, header_2, header_3, _, header_preview = st.columns([2.8, 1, 1, 1, 0.8, 5.2])
    header_n.markdown("**Номер структуры**")
    header_1.markdown("**1**")
    header_2.markdown("**2**")
    header_3.markdown("**3**")
    header_preview.markdown("**output.xyz**")

    open_previews = st.session_state.get("preview_open_outputs", {})

    for n, stages in structures.items():
        col_n, b1, b2, b3, col_vis, col_preview = st.columns([2.8, 1, 1, 1, 0.8, 5.2], gap="small")
        col_n.markdown(f"**{n}**")

        for stage, btn_col in [(1, b1), (2, b2), (3, b3)]:
            info = stages[stage]
            if info["has_output"]:
                if btn_col.button("✅", key=f"open_xyz_{n}_{stage}", help="Открыть output.xyz"):
                    current = open_previews.get(n)
                    if current and current.get("stage") == stage:
                        open_previews.pop(n, None)
                    else:
                        open_previews[n] = {"stage": stage, "path": info["output_xyz"]}
                    st.session_state.preview_open_outputs = open_previews
            else:
                btn_col.markdown("—")

        current_preview = open_previews.get(n)
        if current_preview:
            selected_output = current_preview.get("path", "")
            selected_stage = current_preview.get("stage", "")
            if col_vis.button("🖼️", key=f"preview_vis_btn_{n}_{selected_stage}", type="secondary", help="Визуализировать output.xyz"):
                ok, msg = launch_stmng_visualizer(selected_output, STMNG_XYZ_TEMPLATE_PATH)
                st.toast(msg, icon="✅" if ok else "⚠️")
            col_preview.caption(f"Стадия {selected_stage}")
            col_preview.caption(selected_output)
            try:
                with open(selected_output, "r", encoding="utf-8", errors="replace") as file_obj:
                    output_content = file_obj.read()
                col_preview.code(output_content, language="text")
            except Exception as exc:
                col_preview.error(f"Не удалось открыть output.xyz: {exc}")

def open_in_file_manager(path: str) -> None:
    """Открыть папку/файл в системном проводнике (работает если Streamlit запущен локально)."""
    try:
        if not path or not os.path.exists(path):
            return
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        # не падаем, просто молчим
        pass


def scan_preview_results(workdir: str) -> dict:
    """
    Возвращает структуру:
    {
      "calculation_dir": ".../Calculation",
      "structures": {
         N: {
           1: {"folder": "...", "output_xyz": "...", "has_folder": bool, "has_output": bool},
           2: {...},
           3: {...},
         },
         ...
      }
    }
    """
    calculation_dir = os.path.join(workdir or "", "Calculation")
    structures: dict[int, dict[int, dict]] = {}

    if not workdir or not os.path.isdir(calculation_dir):
        return {"calculation_dir": calculation_dir, "structures": {}}

    try:
        for name in os.listdir(calculation_dir):
            m = _CALCFOLD_RE.match(name)
            if not m:
                continue
            n = int(m.group(1))
            stage = int(m.group(2))
            if stage not in (1, 2, 3):
                continue

            folder = os.path.join(calculation_dir, name)
            out_xyz = os.path.join(folder, "output.xyz")
            structures.setdefault(n, {})
            structures[n][stage] = {
                "folder": folder,
                "output_xyz": out_xyz,
                "has_folder": os.path.isdir(folder),
                "has_output": os.path.isfile(out_xyz),
            }
    except Exception:
        # если внезапно нет доступа/ошибка — просто отдадим то, что есть
        pass

    # гарантируем 1..3 для каждого N (даже если папки нет)
    for n in list(structures.keys()):
        for stage in (1, 2, 3):
            if stage not in structures[n]:
                folder = os.path.join(calculation_dir, f"Calcfold_{n}_{stage}")
                out_xyz = os.path.join(folder, "output.xyz")
                structures[n][stage] = {
                    "folder": folder,
                    "output_xyz": out_xyz,
                    "has_folder": os.path.isdir(folder),
                    "has_output": os.path.isfile(out_xyz),
                }

    return {"calculation_dir": calculation_dir, "structures": dict(sorted(structures.items()))}


def _is_within_root(path: str, root: str) -> bool:
    try:
        path_abs = os.path.abspath(path)
        root_abs = os.path.abspath(root)
        return os.path.commonpath([path_abs, root_abs]) == root_abs
    except Exception:
        return False


def render_folder_browser(root_path: str, current_path: str) -> None:
    root_abs = os.path.abspath(root_path)
    current_abs = os.path.abspath(current_path)

    if not os.path.isdir(root_abs):
        st.error("Корневая папка недоступна.")
        return

    if not os.path.isdir(current_abs) or not _is_within_root(current_abs, root_abs):
        current_abs = root_abs
        st.session_state.browser_current = root_abs

    st.subheader(t("contents_of_folder"))
    st.caption(f"Root: {root_abs}")
    st.caption(f"Current: {current_abs}")

    nav_up_col, nav_root_col = st.columns([1, 1])
    parent_path = os.path.abspath(os.path.join(current_abs, os.pardir))
    can_go_up = current_abs != root_abs and _is_within_root(parent_path, root_abs)

    if nav_up_col.button("⬆️ ..", disabled=not can_go_up, key=f"go_up_{current_abs}"):
        st.session_state.browser_current = parent_path
        st.rerun()

    if nav_root_col.button("🏠 Root", disabled=current_abs == root_abs, key=f"go_root_{root_abs}"):
        st.session_state.browser_current = root_abs
        st.rerun()

    try:
        names = os.listdir(current_abs)
    except Exception as exc:
        st.error(t("failed_to_read_folder_contents").format(exc))
        return

    if not names:
        st.info(t("folder_is_empty"))
        return

    dir_entries = []
    file_entries = []
    for name in names:
        full_path = os.path.join(current_abs, name)
        if os.path.isdir(full_path):
            dir_entries.append((name, full_path))
        else:
            file_entries.append(name)

    dir_entries.sort(key=lambda item: item[0].lower())
    file_entries.sort(key=str.lower)

    for dir_name, dir_path in dir_entries:
        if st.button(f"📁 {dir_name}", key=f"nav_dir_{dir_path}"):
            st.session_state.browser_current = dir_path
            st.rerun()

    for file_name in file_entries:
        full_path = os.path.join(current_abs, file_name)
        c_open, c_view, c_seed, c_name = st.columns([1.4, 1.6, 1.4, 7.6])
        if c_open.button("Открыть", key=f"file_open_{full_path}"):
            if st.session_state.browser_open_text_file == full_path:
                st.session_state.browser_open_text_file = ""
            else:
                st.session_state.browser_open_text_file = full_path
            st.rerun()
        if c_view.button("Посмотреть", key=f"file_view_{full_path}"):
            ok, msg = launch_stmng_visualizer(full_path)
            st.session_state.browser_visualize_status = msg
            if ok:
                st.toast(msg, icon="✅")
            else:
                st.toast(msg, icon="⚠️")
        if c_seed.button("В Seeds!", key=f"file_seed_{full_path}"):
            if st.session_state.browser_seed_target == full_path:
                st.session_state.browser_seed_target = ""
                st.session_state.browser_seed_info = None
                st.session_state.browser_seed_error = ""
            else:
                st.session_state.browser_seed_target = full_path
                try:
                    st.session_state.browser_seed_info = check_structures(full_path)
                    st.session_state.browser_seed_error = ""
                except ValueError as exc:
                    st.session_state.browser_seed_info = None
                    st.session_state.browser_seed_error = str(exc)
            st.rerun()
        c_name.write(f"📄 {file_name}")

        if st.session_state.browser_seed_target == full_path:
            seed_info = st.session_state.browser_seed_info
            with st.container():
                st.caption(full_path)
                if seed_info is None:
                    st.error(st.session_state.get("browser_seed_error", "Не удалось разобрать файл как POSCAR/POSCARS."))
                else:
                    count = int(seed_info.get("Количество структур", 0))
                    elements = seed_info.get("Элементы", [])
                    elements_text = " ".join(elements) if isinstance(elements, list) else ""
                    st.info(f"{count} структур элементы {elements_text}".strip())
                    btn_check, btn_add = st.columns(2)
                    if btn_check.button("Проверить", key=f"seed_check_from_file_{full_path}"):
                        st.json(seed_info)
                    if btn_add.button("Добавить", key=f"seed_add_from_file_{full_path}", type="primary"):
                        ok, msg = add_seed_group_to_state(full_path, "browser")
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.session_state.browser_seed_target = ""
                        st.session_state.browser_seed_info = None
                        st.session_state.browser_seed_error = ""
                        st.rerun()
        if st.session_state.get("browser_open_text_file", "").strip() == full_path:
            with st.container():
                st.caption(full_path)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as file_obj:
                        content = file_obj.read()
                    st.code(content, language="text")
                except Exception as exc:
                    st.error(f"Не удалось открыть файл: {exc}")


def check_structures(poscar_path: str) -> dict[str, object]:
    try:
        with open(poscar_path, "r", encoding="utf-8", errors="replace") as file_obj:
            lines = [line.rstrip("\n") for line in file_obj]
    except Exception as exc:
        raise ValueError(f"Не удалось открыть файл: {exc}") from exc

    i = 0
    n = len(lines)
    structures_count = 0
    all_elements = set()
    systems = set()

    def skip_empty(idx: int) -> int:
        while idx < n and not lines[idx].strip():
            idx += 1
        return idx

    i = skip_empty(i)
    while i < n:
        comment = lines[i].strip()
        if not comment:
            i = skip_empty(i + 1)
            continue
        i = skip_empty(i + 1)
        if i >= n:
            break

        try:
            float(lines[i].split()[0])
        except Exception as exc:
            raise ValueError("Некорректный POSCAR/POSCARS: неверный scale factor.") from exc

        i = skip_empty(i + 1)
        if i + 2 >= n:
            raise ValueError("Некорректный POSCAR/POSCARS: отсутствуют векторы решётки.")
        i = skip_empty(i + 3)
        if i >= n:
            raise ValueError("Некорректный POSCAR/POSCARS: отсутствует строка элементов (VASP-5).")

        toks = lines[i].split()
        has_any_alpha = any(any(ch.isalpha() for ch in token) for token in toks)
        if not has_any_alpha:
            raise ValueError(
                "Поддерживается только формат VASP-5: после решётки должна быть строка символов элементов."
            )
        elem_symbols = toks
        i = skip_empty(i + 1)
        if i >= n:
            raise ValueError("Некорректный POSCAR/POSCARS: отсутствует строка количеств атомов.")
        try:
            counts = [int(x) for x in lines[i].split()]
        except Exception as exc:
            raise ValueError("Некорректный POSCAR/POSCARS: строка количеств атомов должна содержать целые числа.") from exc
        if len(counts) != len(elem_symbols):
            raise ValueError("Некорректный POSCAR/POSCARS: число элементов не совпадает с числом количеств.")
        if any(x <= 0 for x in counts):
            raise ValueError("Некорректный POSCAR/POSCARS: количества атомов должны быть > 0.")
        i += 1

        i = skip_empty(i)
        if i >= n:
            raise ValueError("Некорректный POSCAR/POSCARS: отсутствует режим координат.")
        if lines[i].lower().startswith("s"):
            i = skip_empty(i + 1)
            if i >= n:
                raise ValueError("Некорректный POSCAR/POSCARS: после selective dynamics нет режима координат.")
        if not lines[i].lower().startswith(("d", "c")):
            raise ValueError("Некорректный POSCAR/POSCARS: режим координат должен начинаться с Direct или Cartesian.")

        i = skip_empty(i + 1)
        total_atoms = sum(counts)
        if i + total_atoms > n:
            raise ValueError("Некорректный POSCAR/POSCARS: не хватает строк координат атомов.")
        i += total_atoms

        structures_count += 1
        elems_set = set(elem_symbols)
        all_elements |= elems_set
        systems.add(tuple(sorted(elems_set)))
        i = skip_empty(i)

    if structures_count <= 0:
        raise ValueError("В файле не найдено ни одной корректной структуры POSCAR/POSCARS.")

    return {
        "Количество структур": structures_count,
        "Элементы": sorted(all_elements),
        "Встреченные системы": ["-".join(sys_items) for sys_items in sorted(systems)],
    }


def _formula(elements: list[str], counts: list[int]) -> str:
    return " ".join(f"{el}{c if c != 1 else ''}" for el, c in zip(elements, counts))


def parse_poscars(path: str) -> list[dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as file_obj:
            lines = file_obj.read().splitlines()
    except Exception:
        return []

    n = len(lines)
    i = 0
    out = []
    idx = 0

    def skip_empty(j: int) -> int:
        while j < n and not lines[j].strip():
            j += 1
        return j

    i = skip_empty(i)
    while i < n:
        start = i
        if i + 6 >= n:
            break

        comment = lines[i].strip()
        if not comment:
            i = skip_empty(i + 1)
            continue

        match = _COMMENT_RE.search(comment)
        if match:
            gen_val = int(match.group("Gen"))
            generation = int(match.group("generation"))
            number = int(match.group("number"))
            energy = float(match.group("energy"))
        else:
            gen_val = generation = number = math.nan
            energy = math.nan

        try:
            float(lines[i + 1].split()[0])
            for k in (i + 2, i + 3, i + 4):
                if len(lines[k].split()) < 3:
                    raise ValueError
            elements = lines[i + 5].split()
            counts = [int(x) for x in lines[i + 6].split()]
            total_atoms = sum(counts)

            j = skip_empty(i + 7)
            if j >= n:
                break
            if lines[j].strip().lower().startswith("s"):
                j = skip_empty(j + 1)
                if j >= n:
                    break
            if not lines[j].strip() or lines[j].strip()[0].lower() not in ("d", "c"):
                raise ValueError

            coords_start = skip_empty(j + 1)
            end = coords_start + total_atoms
            if end > n:
                break

            structure_text = "\n".join(lines[start:end])
            idx += 1
            out.append(
                {
                    "номер": idx,
                    "формула": _formula(elements, counts),
                    "Gen": gen_val,
                    "generation": generation,
                    "number": number,
                    "energy": energy,
                    "structure": structure_text,
                }
            )
            i = skip_empty(end)
        except Exception:
            k = start + 1
            while k < n and "Gen=" not in lines[k]:
                k += 1
            if k >= n:
                break
            i = skip_empty(k)

    return out


def _safe_filename_token(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_"))
    return cleaned or "Seeds"


def _next_archive_name(seeds_dir: str, elements: list[str], count: int) -> str:
    base = f"{''.join(elements)}_{count}"
    base = _safe_filename_token(base)
    idx = 1
    while True:
        candidate = os.path.join(seeds_dir, f"{base}_N{idx}")
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def build_seed_group(path: str, group_id: int, source: str) -> dict[str, Any]:
    stats = check_structures(path)
    structures = parse_poscars(path)
    if not structures:
        raise ValueError("Не удалось извлечь структуры из файла POSCAR/POSCARS.")
    return {
        "id": group_id,
        "path": os.path.abspath(path),
        "source": source,
        "stats": stats,
        "structures": structures,
    }


def add_seed_group_to_state(path: str, source: str) -> tuple[bool, str]:
    path = path.strip()
    if not path:
        return False, "Укажите путь к файлу."
    try:
        group = build_seed_group(path, st.session_state.seed_next_group_id, source)
    except ValueError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, f"Не удалось прочитать POSCAR/POSCARS: {exc}"
    st.session_state.seed_next_group_id += 1
    st.session_state.seed_groups.append(group)
    st.session_state.seed_check_info = group.get("stats")
    st.session_state.seed_force_enable = True
    return True, "Файл добавлен в Seeds."


def launch_stmng_visualizer(target_path: str, template_path: str = "") -> tuple[bool, str]:
    template = template_path.strip() if template_path else STMNG_TEMPLATE_PATH
    if not os.path.isfile(target_path):
        return False, "Файл для визуализации не найден."
    if not os.path.isfile(STMNG_EXE_PATH):
        return False, f"Не найден STMng: {STMNG_EXE_PATH}"
    if not os.path.isdir(STMNG_WORKDIR):
        return False, f"Не найдена рабочая папка STMng: {STMNG_WORKDIR}"
    if not os.path.isfile(template):
        return False, f"Не найден шаблон STM: {template}"
    try:
        subprocess.Popen(
            [STMNG_EXE_PATH, "--read", target_path, template],
            cwd=STMNG_WORKDIR,
            close_fds=True,
        )
    except Exception as exc:
        return False, f"Не удалось запустить STMng: {exc}"
    return True, "Визуализатор запущен."


def launch_stmng_visualizer_for_seed_text(workdir: str, content: str, prefix: str) -> tuple[bool, str]:
    if not workdir or not os.path.isdir(workdir):
        return False, "Рабочая папка недоступна для временного файла визуализации."
    text = content.strip()
    if not text:
        return False, "Нет данных для визуализации."

    seeds_dir = os.path.join(workdir, "Seeds")
    os.makedirs(seeds_dir, exist_ok=True)
    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix=f"{prefix}_",
            suffix=".POSCARS",
            dir=seeds_dir,
            text=True,
        )
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file_obj:
            file_obj.write(text)
            file_obj.write("\n")

        ok, msg = launch_stmng_visualizer(tmp_path)
        if not ok:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return False, msg

        pending = st.session_state.get("seed_tmp_cleanup_paths", [])
        pending.append({"path": tmp_path, "delete_after": time.time() + 10.0})
        st.session_state.seed_tmp_cleanup_paths = pending
        return True, msg
    except Exception as exc:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False, f"Не удалось подготовить временный файл визуализации: {exc}"


def cleanup_seed_tmp_files() -> None:
    pending = list(st.session_state.get("seed_tmp_cleanup_paths", []))
    if not pending:
        return
    remaining = []
    now_ts = time.time()
    for item in pending:
        if isinstance(item, dict):
            path = str(item.get("path", ""))
            delete_after = float(item.get("delete_after", 0.0) or 0.0)
        else:
            # backward compatibility with older state format
            path = str(item)
            delete_after = 0.0
        if not path:
            continue
        if now_ts < delete_after:
            remaining.append({"path": path, "delete_after": delete_after})
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            remaining.append({"path": path, "delete_after": now_ts + 3.0})
    st.session_state.seed_tmp_cleanup_paths = remaining


def fetch_mp_seed_group(
    api_key: str,
    chemsys: str,
    ehull_max_text: str,
    group_id: int,
) -> tuple[bool, str, dict[str, Any] | None]:
    api_key = api_key.strip()
    chemsys = chemsys.strip()
    if not api_key:
        return False, "Сначала укажите API-ключ Materials Project.", None
    if not chemsys or "-" not in chemsys:
        return False, "Укажите систему в формате через '-', например Fe-O.", None
    ehull_label = ehull_max_text.strip()
    try:
        ehull_max = float(ehull_label)
        if ehull_max < 0:
            return False, "Порог e_above_hull должен быть >= 0.", None
    except Exception:
        return False, "Некорректный порог e_above_hull.", None

    try:
        from mp_api.client import MPRester
        from pymatgen.io.vasp import Poscar
    except Exception as exc:
        return False, f"Не хватает зависимостей mp_api/pymatgen: {exc}", None

    try:
        with MPRester(api_key) as mpr:
            search_fn = mpr.materials.summary.search
            common_kwargs = {
                "chemsys": chemsys,
                "fields": ["material_id", "structure"],
                "chunk_size": 50,
            }
            docs = None
            last_exc = None

            # mp_api versions differ on the hull filter argument name.
            for hull_arg_name in ("energy_above_hull", "e_above_hull"):
                kwargs = dict(common_kwargs)
                kwargs[hull_arg_name] = (0, ehull_max)
                try:
                    docs = search_fn(**kwargs)
                    break
                except TypeError as exc:
                    last_exc = exc
                    continue
                except Exception as exc:
                    msg = str(exc)
                    if "unknown to" in msg and hull_arg_name in msg:
                        last_exc = exc
                        continue
                    raise

            if docs is None:
                if last_exc is not None:
                    raise last_exc
                raise ValueError(
                    "Не удалось определить параметр фильтра по энергии hull для текущей версии mp_api."
                )
    except Exception as exc:
        return False, f"Ошибка запроса к Materials Project: {exc}", None

    if not docs:
        return False, "По заданным условиям структуры не найдены.", None

    structures: list[dict[str, Any]] = []
    all_elements: set[str] = set()
    systems: set[tuple[str, ...]] = set()
    for idx, doc in enumerate(docs, start=1):
        poscar = Poscar(doc.structure)
        elements = [str(x) for x in poscar.site_symbols]
        counts = [int(x) for x in poscar.natoms]
        structure_text = poscar.get_str().rstrip()
        structures.append(
            {
                "номер": idx,
                "формула": _formula(elements, counts),
                "Gen": math.nan,
                "generation": math.nan,
                "number": math.nan,
                "energy": math.nan,
                "structure": structure_text,
            }
        )
        elems_set = set(elements)
        all_elements |= elems_set
        systems.add(tuple(sorted(elems_set)))

    stats = {
        "Количество структур": len(structures),
        "Элементы": sorted(all_elements),
        "Встреченные системы": ["-".join(sys_items) for sys_items in sorted(systems)],
    }
    group = {
        "id": group_id,
        "path": f"Materials Project ({chemsys})",
        "source": "mp",
        "source_label": f"mp < Energy Above Hull ({ehull_label})",
        "stats": stats,
        "structures": structures,
    }
    return True, f"Materials Project: добавлено {len(docs)} структур в Seeds.", group


def seed_group_summary(group: dict[str, Any]) -> str:
    stats = group.get("stats", {})
    count = int(stats.get("Количество структур", 0))
    elements = stats.get("Элементы", [])
    elems_text = " ".join(elements) if isinstance(elements, list) else ""
    source_label = str(group.get("source_label", "")).strip()
    base = f"{count} структур элементы {elems_text}".strip()
    if source_label:
        return f"{source_label} | {base}"
    return base


def ensure_seeds_export(workdir: str, seed_groups: list[dict[str, Any]]) -> None:
    seeds_dir = os.path.join(workdir, "Seeds")
    os.makedirs(seeds_dir, exist_ok=True)
    out_path = os.path.join(seeds_dir, "POSCARS")
    chunks = []
    if os.path.isfile(out_path):
        try:
            with open(out_path, "r", encoding="utf-8", errors="replace") as file_obj:
                existing = file_obj.read().strip()
            if existing:
                chunks.append(existing)
        except Exception:
            pass
    out_abs = os.path.abspath(out_path)
    for group in seed_groups:
        group_path = os.path.abspath(str(group.get("path", "")))
        if group_path == out_abs:
            continue
        for item in group.get("structures", []):
            text = item.get("structure", "")
            if text:
                chunks.append(text.rstrip())
    with open(out_path, "w", encoding="utf-8") as file_obj:
        file_obj.write("\n".join(chunks))

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
    "elements": {
        "ru": "Элементы или формулы через пробел",
        "en": "Elements or formulas (space-separated)",
        "zh": "元素或化学式（空格分隔）",
    },
    "counts": {"ru": "Число атомов по элементам", "en": "Counts per element", "zh": "每种元素原子数"},
    "ratios": {"ru": "Соотношение (целые числа)", "en": "Ratios (integers)", "zh": "比例（整数）"},
    "min_at": {"ru": "minAt", "en": "minAt", "zh": "minAt"},
    "max_at": {"ru": "maxAt", "en": "maxAt", "zh": "maxAt"},
    "advanced": {"ru": "Расширенные параметры", "en": "Advanced parameters", "zh": "高级参数"},
    "preview": {"ru": "Предпросмотр INPUT.txt", "en": "INPUT.txt preview", "zh": "INPUT.txt 预览"},
    "run": {"ru": "Запустить", "en": "Run", "zh": "运行"},
    "stop": {"ru": "Остановить", "en": "Stop", "zh": "停止"},
    "stop_label": {"ru": "Остановить ⚠️", "en": "Stop ⚠️", "zh": "停止 ⚠️"},
    "status": {"ru": "Статус", "en": "Status", "zh": "状态"},
    "generation": {"ru": "Поколение", "en": "Generation", "zh": "代"},
    "stage": {"ru": "Стадия", "en": "Stage", "zh": "阶段"},
    "done": {"ru": "Сделано", "en": "Done", "zh": "完成"},
    "total": {"ru": "Всего", "en": "Total", "zh": "总计"},
    "gen_size": {"ru": "Размер поколения", "en": "Gen size", "zh": "代大小"},
    "log": {"ru": "Лог", "en": "Log", "zh": "日志"},
    "stop_help": {
        "ru": "Данная опция находится в разработке, для остановки процесса откройте Диспетчер задач, сначала остановите процесс uspex.exe, а затем процессы relaxation.py. ВНИМАНИЕ! данные текущего поколения будут потеряны, возможно имеет смысл дождаться расчёта поколения",
        "en": "This option is under development. To stop the process, open Task Manager, stop uspex.exe first, then stop relaxation.py processes. WARNING! Current generation data will be lost; it may be better to wait for the generation to finish.",
        "zh": "此功能正在开发中。如需停止，请打开任务管理器，先结束 uspex.exe，再结束 relaxation.py 进程。警告：当前代数据将丢失，可能更合理的是等待本代计算完成。",
    },
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
    "reset_defaults": {
        "ru": "Значения по умолчанию",
        "en": "Default values",
        "zh": "默认值",
    },
    "config_found": {
        "ru": "Обнаружен файл конфигурации. Загрузить сохранённые параметры?",
        "en": "Configuration file found. Load saved parameters?",
        "zh": "检测到配置文件。加载已保存的参数？",
    },
    "config_load": {
        "ru": "Загрузить",
        "en": "Load",
        "zh": "加载",
    },
    "config_ignore": {
        "ru": "Не сейчас",
        "en": "Not now",
        "zh": "暂不",
    },
    "config_missing": {
        "ru": "Файл конфигурации не найден.",
        "en": "Configuration file not found.",
        "zh": "未找到配置文件。",
    },
    "go_latest": {
        "ru": "К актуальным изменениям",
        "en": "Go to latest",
        "zh": "跳到最新",
    },
    "view_preview_results_header": {
        "ru": "Результаты",
        "en": "Results",
        "zh": "结果",
    },
    "view_preview_results": {
        "ru": "Предв. результаты",
        "en": "Preview results",
        "zh": "预览结果",
    },
    "view_all_jobs": {
        "ru": "Все работы",
        "en": "All jobs",
        "zh": "所有任务",
    },
    "choose_directory": {
        "ru": "Выбрать директорию",
        "en": "Choose folder",
        "zh": "选择目录",
    },
    "insert_local_path": {
        "ru": "Вставьте локальный путь",
        "en": "Insert local path",
        "zh": "插入本地路径",
    },
    "example_path": {
        "ru": "C:\\Users\\... или /Users/...",
        "en": "C:\\Users\\... or /Users/...",
        "zh": "C:\\Users\\... 或 /Users/...",
    },
    "add_folder": {
        "ru": "Добавить",
        "en": "Add",
        "zh": "添加",
    },
    "path_cannot_be_empty": {
        "ru": "Путь не может быть пустым.",
        "en": "Path cannot be empty.",
        "zh": "路径不能为空。",
    },
    "folder_does_not_exist": {
        "ru": "Такой папки не существует. Проверьте путь.",
        "en": "Such folder does not exist. Check the path.",
        "zh": "该文件夹不存在。请检查路径。",
    },
    "folder_already_added": {
        "ru": "Эта папка уже добавлена.",
        "en": "This folder has already been added.",
        "zh": "此文件夹已添加。",
    },
    "contents_of_folder": {
        "ru": "Содержимое папки:",
        "en": "Contents of folder:",
        "zh": "文件夹内容:",
    },
    "folder_is_empty": {
        "ru": "Эта папка пуста.",
        "en": "This folder is empty.",
        "zh": "此文件夹为空。",
    },
    "failed_to_read_folder_contents": {
        "ru": "Не удалось прочитать содержимое папки. Ошибка: {0}",
        "en": "Failed to read folder contents. Error: {0}",
        "zh": "无法读取文件夹内容。错误: {0}",
    },
    "select_added_folder_to_view_contents": {
        "ru": "Выберите добавленную папку, чтобы просмотреть её содержимое.",
        "en": "Select an added folder to view its contents.",
        "zh": "请选择已添加的文件夹以查看其内容。",
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

DEFAULT_ELEMENTS_TEXT = "Si O"
DEFAULT_COUNTS_TEXT = "6 12"
DEFAULT_RATIOS_TEXT = "1 2"
DEFAULT_MIN_AT_TEXT = "8"
DEFAULT_MAX_AT_TEXT = "18"
DEFAULT_ADVANCED_PARAMS = {
    "populationSize": "80",
    "initialPopSize": "200",
    "numGenerations": "60",
    "stopCrit": "20",
}


def _pink_bloom_bg(primary: str) -> str:
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='180' height='180' viewBox='0 0 180 180'
         fill='none' stroke='{primary}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'
         opacity='0.35'>
      <path d='M30 48 C30 40 38 35 45 39 C52 29 66 35 66 48 C66 62 48 74 48 74 C48 74 30 62 30 48 Z'/>
      <circle cx='132' cy='46' r='12'/>
      <path d='M120 46 L110 38 M120 46 L110 54 M144 46 L154 38 M144 46 L154 54'/>
      <path d='M36 132 Q60 104 84 132 Z'/>
      <path d='M40 132 L80 132 M46 132 L46 146 M60 132 L60 146 M74 132 L74 146'/>
      <path d='M110 124 C110 116 118 112 125 116 C132 108 144 112 144 124 C144 136 127 146 127 146 C127 146 110 136 110 124 Z'/>
      <path d='M92 70 L100 62 L108 70 L100 78 Z'/>
    </svg>
    """
    svg = " ".join(line.strip() for line in svg.splitlines())
    return urllib.parse.quote(svg)


def apply_theme(primary: str, bg: str, text: str, task_text: str, theme_name: str | None = None) -> None:
    bg_image = ""
    if theme_name == "Pink Bloom":
        bg_image = (
            "background-image: url(\"data:image/svg+xml;utf8,"
            + _pink_bloom_bg(primary)
            + "\");"
            "background-size: 180px 180px;"
            "background-repeat: repeat;"
            "background-attachment: fixed;"
        )
    css = f"""
    <style>
    .stApp {{
        background: {bg};
        color: {text};
        {bg_image}
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


def default_params() -> dict:
    return {
        "elements_text": DEFAULT_ELEMENTS_TEXT,
        "counts_text": DEFAULT_COUNTS_TEXT,
        "ratios_text": DEFAULT_RATIOS_TEXT,
        "min_at_text": DEFAULT_MIN_AT_TEXT,
        "max_at_text": DEFAULT_MAX_AT_TEXT,
    }


def default_advanced_params() -> dict:
    return dict(DEFAULT_ADVANCED_PARAMS)


def append_advanced_params(text: str, params: dict, enabled: bool) -> str:
    if not enabled:
        return text
    lines = []
    for name in DEFAULT_ADVANCED_PARAMS.keys():
        value = str(params.get(name, "")).strip()
        if value:
            lines.append(f"{value} : {name}")
    if not lines:
        return text
    out = text or ""
    if out:
        if not out.endswith("\n"):
            out += "\n"
        if not out.endswith("\n\n"):
            out += "\n"
    out += "\n".join(lines)
    return out


def build_mode_state(mode: str, data: dict | None = None) -> dict:
    data = data or {}
    params = default_params()
    for key in ["elements_text", "counts_text", "ratios_text", "min_at_text", "max_at_text"]:
        if key in data and data[key] is not None:
            params[key] = data[key]
    advanced_params = default_advanced_params()

    if isinstance(data.get("advanced_params"), dict):
        for key in DEFAULT_ADVANCED_PARAMS:
            v = data["advanced_params"].get(key)
            if v is None:
                continue
            v = str(v).strip()
            if v == "":
                continue  # пустое НЕ перетирает дефолт
            advanced_params[key] = v

    advanced_enabled = bool(data.get("advanced_enabled", False))
    try:
        expected_text = run_selected_mode(
            mode,
            params["elements_text"],
            params["counts_text"],
            params["ratios_text"],
            params["min_at_text"],
            params["max_at_text"],
        )
    except Exception as exc:
        expected_text = f"(input error: {exc})"
    expected_text = append_advanced_params(expected_text, advanced_params, advanced_enabled)
    input_preview = data.get("input_preview")
    preview_dirty = bool(data.get("preview_dirty", False))
    last_expected = data.get("last_expected")
    if input_preview is None:
        input_preview = expected_text
    if last_expected is None:
        last_expected = expected_text
    return {
        "elements_text": params["elements_text"],
        "counts_text": params["counts_text"],
        "ratios_text": params["ratios_text"],
        "min_at_text": params["min_at_text"],
        "max_at_text": params["max_at_text"],
        "advanced_enabled": advanced_enabled,
        "advanced_params": advanced_params,
        "input_preview": input_preview,
        "preview_dirty": preview_dirty,
        "last_expected": last_expected,
    }


def ensure_mode_states() -> None:
    state = st.session_state.get("mode_state", {})
    for mode in ["fixed", "single", "variable"]:
        state[mode] = build_mode_state(mode, state.get(mode, {}))
    st.session_state.mode_state = state
    for mode in ["fixed", "single", "variable"]:
        key = f"adv_toggle_{mode}"
        if key not in st.session_state:
            st.session_state[key] = state[mode]["advanced_enabled"]


def save_current_mode_state(mode: str) -> None:
    prev = st.session_state.mode_state.get(mode, {})
    advanced_params = dict(prev.get("advanced_params", DEFAULT_ADVANCED_PARAMS))

    for name in DEFAULT_ADVANCED_PARAMS.keys():
        k = f"adv_{name}"
        if k in st.session_state:           # сохраняем только если реально есть
            v = str(st.session_state[k]).strip()
            if v != "":
                advanced_params[name] = v   # обновляем
            else:
                # если пользователь оставил пустым — можно оставить как есть
                # или явным образом записывать "", если тебе это нужно
                pass

    st.session_state.mode_state[mode] = {
        "elements_text": st.session_state.elements_text,
        "counts_text": st.session_state.counts_text,
        "ratios_text": st.session_state.ratios_text,
        "min_at_text": st.session_state.min_at_text,
        "max_at_text": st.session_state.max_at_text,
        "advanced_enabled": st.session_state.get(f"adv_toggle_{mode}", False),
        "advanced_params": advanced_params,
        "input_preview": st.session_state.input_preview,
        "preview_dirty": st.session_state.preview_dirty,
        "last_expected": st.session_state.last_expected,
    }


def load_mode_state(mode: str) -> None:
    state = st.session_state.mode_state.get(mode, build_mode_state(mode))
    st.session_state.elements_text = state["elements_text"]
    st.session_state.counts_text = state["counts_text"]
    st.session_state.ratios_text = state["ratios_text"]
    st.session_state.min_at_text = state["min_at_text"]
    st.session_state.max_at_text = state["max_at_text"]
    st.session_state[f"adv_toggle_{mode}"] = state["advanced_enabled"]

    for name in DEFAULT_ADVANCED_PARAMS:
        v = state["advanced_params"].get(name)
        v = "" if v is None else str(v).strip()
        st.session_state[f"adv_{name}"] = v if v != "" else DEFAULT_ADVANCED_PARAMS[name]


    st.session_state.input_preview = state["input_preview"]
    st.session_state.preview_dirty = state["preview_dirty"]
    st.session_state.last_expected = state["last_expected"]


def switch_mode(target: str) -> None:
    current = st.session_state.mode
    save_current_mode_state(current)
    st.session_state.mode = target
    st.session_state.pending_mode = target
    st.rerun()


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
    st.session_state.setdefault("exe_path", logic.DEFAULT_USPEX_EXE)
    st.session_state.setdefault("workdir", "")
    st.session_state.setdefault("theme", THEMES[0])
    st.session_state.setdefault(
        "custom_theme",
        {"primary": "#445566", "bg": "#F7F7F2", "text": "#1E1E1E", "task_text": "#1E1E1E"},
    )
    st.session_state.setdefault("language", "ru")
    st.session_state.setdefault("mode", "fixed")
    st.session_state.setdefault("elements_text", DEFAULT_ELEMENTS_TEXT)
    st.session_state.setdefault("counts_text", DEFAULT_COUNTS_TEXT)
    st.session_state.setdefault("ratios_text", DEFAULT_RATIOS_TEXT)
    st.session_state.setdefault("min_at_text", DEFAULT_MIN_AT_TEXT)
    st.session_state.setdefault("max_at_text", DEFAULT_MAX_AT_TEXT)
    st.session_state.setdefault("input_preview", "")
    st.session_state.setdefault("preview_dirty", False)
    st.session_state.setdefault("last_expected", "")
    st.session_state.setdefault("mode_state", {})
    st.session_state.setdefault("config_choice", None)
    st.session_state.setdefault("config_loaded", False)
    st.session_state.setdefault("initialized_defaults", False)
    st.session_state.setdefault("config_reset_error", False)
    st.session_state.setdefault("pending_mode", None)
    st.session_state.setdefault("view", "main")  # "main" | "preview_results"
    st.session_state.setdefault("preview_results_cache", None)
    st.session_state.setdefault("seeds_enabled", False)
    st.session_state.setdefault("seed_groups", [])
    st.session_state.setdefault("seed_next_group_id", 1)
    st.session_state.setdefault("seed_input_path", "")
    st.session_state.setdefault("seed_check_info", None)
    st.session_state.setdefault("seed_existing_candidates", [])
    st.session_state.setdefault("seed_scanned_workdir", "")
    st.session_state.setdefault("seed_candidates_toast_tag", "")
    st.session_state.setdefault("seed_confirm_delete_group", None)
    st.session_state.setdefault("seed_confirm_delete_structure", None)
    st.session_state.setdefault("seed_clear_input", False)
    st.session_state.setdefault("seed_force_enable", False)
    st.session_state.setdefault("seed_check_error", "")
    st.session_state.setdefault("browser_open_text_file", "")
    st.session_state.setdefault("browser_seed_target", "")
    st.session_state.setdefault("browser_seed_info", None)
    st.session_state.setdefault("browser_seed_error", "")
    st.session_state.setdefault("browser_visualize_status", "")
    st.session_state.setdefault("materials_project_api_key", "")
    st.session_state.setdefault("mp_chemsys", "Fe-O")
    st.session_state.setdefault("mp_ehull_max", "0.10")
    st.session_state.setdefault("seed_tmp_cleanup_paths", [])

    if not st.session_state.initialized_defaults:
        ensure_mode_states()
        load_mode_state(st.session_state.mode)
        st.session_state.initialized_defaults = True


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
    # Единственный источник правды: st.session_state["language"]
    if "language" not in st.session_state:
        st.session_state["language"] = "ru"

    st.markdown(f"### {t('language')}")

    codes = list(LANGUAGES.keys())
    st.selectbox(
        t("language"),
        codes,
        index=codes.index(st.session_state["language"]),
        key="language",
        format_func=lambda code: f"{LANGUAGES[code]['flag']} {LANGUAGES[code]['name']}",
        label_visibility="collapsed",
    )



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

    if "theme_name" not in st.session_state:
        # Инициализируем из текущего st.session_state.theme
        if st.session_state.theme == "custom":
            st.session_state.theme_name = "Custom"
        else:
            st.session_state.theme_name = st.session_state.theme["name"]

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

    pick = st.selectbox(
        title,
        theme_names,
        index=theme_names.index(st.session_state.theme_name),
        key="theme_name",  # <- один ключ, одна правда
        format_func=lambda name: f"{theme_icons.get(name, '⬜')} {name}",
        label_visibility="collapsed",
    )

    # Преобразуем выбранное имя в реальную тему и применяем
    if pick == "Custom":
        st.session_state.theme = "custom"

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
            None,
        )
    else:
        theme = next(t for t in THEMES if t["name"] == pick)
        st.session_state.theme = theme
        apply_theme(theme["primary"], theme["bg"], theme["text"], theme["text"], theme["name"])

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


def reset_preview(expected_text: str) -> None:
    st.session_state.input_preview = expected_text
    st.session_state.preview_dirty = False
    st.session_state.last_expected = expected_text


def reset_from_config() -> None:
    config = load_config()
    if not config:
        st.session_state.config_reset_error = True
        st.rerun()
        return
    st.session_state.config_reset_error = False
    mode = st.session_state.mode
    data = {}
    if isinstance(config.get("mode_state"), dict):
        data = config["mode_state"].get(mode, {})
    else:
        legacy_mode = config.get("mode", "fixed")
        legacy_map = {
            "Fixed composition": "fixed",
            "Single block": "single",
            "Variable composition": "variable",
        }
        legacy_mode = legacy_map.get(legacy_mode, legacy_mode)
        if mode == legacy_mode:
            data = {
                "elements_text": config.get("elements_text"),
                "counts_text": config.get("counts_text"),
                "ratios_text": config.get("ratios_text"),
                "min_at_text": config.get("min_at_text"),
                "max_at_text": config.get("max_at_text"),
            }
    state = build_mode_state(mode, data)
    state["input_preview"] = state["last_expected"]
    state["preview_dirty"] = False
    st.session_state.mode_state[mode] = state
    st.session_state.pending_mode = mode
    save_config_state()
    st.rerun()


def reset_defaults() -> None:
    mode = st.session_state.mode
    st.session_state.mode_state[mode] = build_mode_state(mode, {})
    st.session_state.pending_mode = mode
    save_config_state()
    st.rerun()


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
    if mode == "fixed":
        elements = logic.parse_elements(elements_text)
        counts = logic.parse_int_list(counts_text)
        return logic.build_input_fixed(elements, counts)
    if mode == "single":
        elements = logic.parse_elements(elements_text)
        ratios = logic.parse_int_list(ratios_text)
        min_at = int(min_at_text)
        max_at = int(max_at_text)
        return logic.build_input_single(elements, ratios, min_at, max_at)
    min_at = int(min_at_text)
    max_at = int(max_at_text)
    return logic.build_input_variable(elements_text, min_at, max_at)


def apply_config(config: dict) -> None:
    st.session_state.exe_path = config.get("exe_path") or logic.DEFAULT_USPEX_EXE
    st.session_state.workdir = config.get("workdir") or ""
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

    mode_state = {}
    if isinstance(config.get("mode_state"), dict):
        for mode in ["fixed", "single", "variable"]:
            mode_state[mode] = build_mode_state(mode, config["mode_state"].get(mode, {}))
    else:
        legacy = {
            "elements_text": config.get("elements_text"),
            "counts_text": config.get("counts_text"),
            "ratios_text": config.get("ratios_text"),
            "min_at_text": config.get("min_at_text"),
            "max_at_text": config.get("max_at_text"),
        }
        legacy_mode = config.get("mode", "fixed")
        legacy_map = {
            "Fixed composition": "fixed",
            "Single block": "single",
            "Variable composition": "variable",
        }
        legacy_mode = legacy_map.get(legacy_mode, legacy_mode)
        for mode in ["fixed", "single", "variable"]:
            data = legacy if mode == legacy_mode else {}
            mode_state[mode] = build_mode_state(mode, data)
    st.session_state.mode_state = mode_state

    selected_mode = config.get("mode", "fixed")
    legacy_map = {
        "Fixed composition": "fixed",
        "Single block": "single",
        "Variable composition": "variable",
    }
    selected_mode = legacy_map.get(selected_mode, selected_mode)
    if selected_mode not in ["fixed", "single", "variable"]:
        selected_mode = "fixed"
    st.session_state.mode = selected_mode
    load_mode_state(selected_mode)
    st.session_state.materials_project_api_key = config.get("materials_project_api_key", "")
    st.session_state.config_loaded = True
    st.session_state.config_choice = "loaded"


def save_config_state() -> None:
    save_current_mode_state(st.session_state.mode)
    theme_value = "custom" if st.session_state.theme == "custom" else st.session_state.theme["name"]
    config = {
        "exe_path": st.session_state.get("exe_path", ""),
        "workdir": st.session_state.get("workdir", ""),
        "elements_text": st.session_state.get("elements_text", ""),
        "counts_text": st.session_state.get("counts_text", ""),
        "ratios_text": st.session_state.get("ratios_text", ""),
        "min_at_text": st.session_state.get("min_at_text", ""),
        "max_at_text": st.session_state.get("max_at_text", ""),
        "mode": st.session_state.mode,
        "theme": theme_value,
        "custom_theme": st.session_state.custom_theme,
        "language": st.session_state.language,
        "mode_state": st.session_state.mode_state,
        "materials_project_api_key": st.session_state.get("materials_project_api_key", ""),
    }
    save_config(config)


def main() -> None:
    init_state()
    cleanup_seed_tmp_files()
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

        /* Results tabs: scoped only to the three buttons right after the anchor */
        #results-tabs-anchor { height: 0; }
        div.element-container:has(#results-tabs-anchor) + div.element-container
            div[data-testid="stHorizontalBlock"] {
            display: inline-flex !important;
            width: fit-content !important;
            max-width: 100%;
            gap: 2px !important;
            align-items: center;
            padding: 4px 4px;
            border: 1px solid rgba(0,0,0,0.10);
            border-radius: 10px;
            background: rgba(0,0,0,0.02);
            margin-top: 6px;
            white-space: nowrap;
        }
        div.element-container:has(#results-tabs-anchor) + div.element-container
            div[data-testid="column"] {
            flex: 0 0 auto !important;
            width: auto !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
        div.element-container:has(#results-tabs-anchor) + div.element-container
            div[data-testid="stButton"] {
            margin: 0 !important;
            padding: 0 !important;
        }
        div.element-container:has(#results-tabs-anchor) + div.element-container
            div[data-testid="stButton"] > button {
            min-width: 0 !important;
            width: auto !important;
            padding: 4px 8px !important;
            height: 28px !important;
            font-size: 14px !important;
            line-height: 1.2 !important;
            border-radius: 10px 10px 0 0;
            border: 1px solid rgba(0,0,0,0.18);
            background: rgba(255,255,255,0.7);
            color: inherit;
        }
        div.element-container:has(#results-tabs-anchor) + div.element-container
            div[data-testid="stButton"] > button:focus {
            outline: none !important;
            box-shadow: none !important;
        }
        /* Plus tab: last button in the group */
        div.element-container:has(#results-tabs-anchor) + div.element-container
            div[data-testid="column"]:last-child div[data-testid="stButton"] > button {
            width: 28px !important;
            padding: 0 !important;
            border-radius: 10px;
            border: 1px dashed rgba(0,0,0,0.28);
            background: rgba(255,255,255,0.5);
            font-size: 18px !important;
            line-height: 1 !important;
            color: #111;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    

    config = load_config()
    if config and st.session_state.config_choice is None:
        st.warning(t("config_found"))
        c1, c2 = st.columns([1, 1])
        if c1.button(t("config_load"), key="config_load_btn"):
            apply_config(config)
            st.rerun()
        if c2.button(t("config_ignore"), key="config_ignore_btn"):
            st.session_state.config_choice = "ignored"
    elif not config and st.session_state.config_choice is None:
        st.session_state.config_choice = "ignored"

    if st.session_state.pending_mode:
        ensure_mode_states()
        load_mode_state(st.session_state.pending_mode)
        st.session_state.pending_mode = None
        save_config_state()

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
        key="exe_path",
    )
    col2.button(t("browse_exe"), on_click=on_pick_exe)

    col3, col4 = st.columns([4, 1])
    workdir = col3.text_input(t("workdir"), key="workdir")
    col4.button(t("browse_folder"), on_click=on_pick_workdir)

    st.markdown(f"### {t('mode')}")
    mode_labels = [MODE_LABELS[m].get(st.session_state.language, MODE_LABELS[m]["en"]) for m in ["fixed", "single", "variable"]]
    cols = st.columns(3)
    for i, m in enumerate(["fixed", "single", "variable"]):
        label = mode_labels[i]
        if st.session_state.mode == m:
            label = f"✅ {label}"
        with cols[i]:
            enabled = st.checkbox(
                t("advanced"),
                key=f"adv_toggle_{m}",
            )
            st.session_state.mode_state[m]["advanced_enabled"] = enabled
            if st.button(
                label,
                key=f"mode_btn_{m}",
                help=MODE_HELP[m].get(st.session_state.language, MODE_HELP[m]["en"]),
                use_container_width=True,
            ):
                switch_mode(m)
    mode = st.session_state.mode

    elements_text = st.text_input(
        t("elements"),
        key="elements_text",
    )

    counts_text = ""
    ratios_text = ""
    min_at_text = DEFAULT_MIN_AT_TEXT
    max_at_text = DEFAULT_MAX_AT_TEXT

    if mode == "fixed":
        counts_text = st.text_input(
            t("counts"),
            key="counts_text",
        )
    elif mode == "single":
        ratios_text = st.text_input(
            t("ratios"),
            key="ratios_text",
        )
        min_at_text = st.text_input(
            t("min_at"),
            key="min_at_text",
        )
        max_at_text = st.text_input(
            t("max_at"),
            key="max_at_text",
        )
    else:
        min_at_text = st.text_input(
            t("min_at"),
            key="min_at_text",
        )
        max_at_text = st.text_input(
            t("max_at"),
            key="max_at_text",
        )

    if st.session_state.get(f"adv_toggle_{mode}", False):
        st.markdown(f"### {t('advanced')}")
        cur_adv = st.session_state.mode_state.get(mode, {}).get("advanced_params", DEFAULT_ADVANCED_PARAMS)

        for name in DEFAULT_ADVANCED_PARAMS:
            if f"adv_{name}" not in st.session_state:
                v = cur_adv.get(name)
                v = "" if v is None else str(v).strip()
                st.session_state[f"adv_{name}"] = v if v != "" else DEFAULT_ADVANCED_PARAMS[name]

        for name in DEFAULT_ADVANCED_PARAMS:
            st.text_input(name, key=f"adv_{name}")

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
    expected_text = append_advanced_params(
        expected_text,
         {name: st.session_state.get(f"adv_{name}", DEFAULT_ADVANCED_PARAMS[name]) for name in DEFAULT_ADVANCED_PARAMS},
        st.session_state.get(f"adv_toggle_{mode}", False),
    )
    if "input_preview" not in st.session_state or st.session_state.input_preview == "":
        st.session_state.input_preview = expected_text
        st.session_state.preview_dirty = False
        st.session_state.last_expected = expected_text

    if st.session_state.last_expected != expected_text and not st.session_state.preview_dirty:
        st.session_state.input_preview = expected_text

    st.session_state.preview_dirty = st.session_state.input_preview != expected_text
    st.session_state.last_expected = expected_text




    st.text_area(t("preview"), height=200, key="input_preview")
    

    if st.session_state.preview_dirty:
        st.info(t("preview_source"))
        st.button(t("reset_preview"), on_click=reset_preview, args=(expected_text,))
        if st.session_state.config_reset_error:
            st.warning(t("config_missing"))

    st.button(t("reset_defaults"), on_click=reset_defaults)

    if st.session_state.seed_force_enable:
        st.session_state.seeds_enabled = True
        st.session_state.seed_force_enable = False
    st.checkbox("Добавить Seeds", key="seeds_enabled")
    if st.session_state.seeds_enabled:
        if not workdir.strip() or not os.path.isdir(workdir.strip()):
            st.warning("Сначала укажите рабочую папку, потом включайте Seeds.")
            st.session_state.seeds_enabled = False
        else:
            workdir_abs = os.path.abspath(workdir.strip())
            seeds_dir = os.path.join(workdir_abs, "Seeds")

            if st.session_state.seed_scanned_workdir != workdir_abs:
                st.session_state.seed_groups = []
                st.session_state.seed_existing_candidates = []
                st.session_state.seed_check_info = None
                st.session_state.seed_check_error = ""
                st.session_state.seed_confirm_delete_group = None
                st.session_state.seed_confirm_delete_structure = None

                if os.path.isdir(seeds_dir):
                    candidates = []
                    for name in sorted(os.listdir(seeds_dir), key=str.lower):
                        full_path = os.path.join(seeds_dir, name)
                        if not os.path.isfile(full_path):
                            continue
                        try:
                            group = build_seed_group(full_path, st.session_state.seed_next_group_id, "existing")
                        except ValueError:
                            continue
                        st.session_state.seed_next_group_id += 1
                        candidates.append(group)
                    st.session_state.seed_existing_candidates = candidates
                st.session_state.seed_scanned_workdir = workdir_abs

            if st.session_state.seed_clear_input:
                st.session_state.seed_input_path = ""
                st.session_state.seed_clear_input = False

            path_col, mp_col = st.columns([1, 1])
            with path_col.popover("Указать путь", use_container_width=False):
                st.text_input("Путь к файлу POSCAR/POSCARS", key="seed_input_path")
                btn_check, btn_add = st.columns(2)
                if btn_check.button("Проверить структуры", key="seed_check_btn"):
                    try:
                        info = check_structures(st.session_state.seed_input_path.strip())
                        st.session_state.seed_check_info = info
                        st.session_state.seed_check_error = ""
                    except ValueError as exc:
                        st.session_state.seed_check_info = None
                        st.session_state.seed_check_error = str(exc)
                if btn_add.button("Добавить", key="seed_add_btn", type="primary"):
                    input_path = st.session_state.seed_input_path.strip()
                    ok, msg = add_seed_group_to_state(input_path, "manual")
                    if ok:
                        st.session_state.seed_clear_input = True
                        st.session_state.seed_check_error = ""
                        st.rerun()
                    else:
                        st.error(msg)
                if st.session_state.seed_check_info is None:
                    if st.session_state.seed_check_error:
                        st.error(st.session_state.seed_check_error)
                    else:
                        st.info("Нажмите 'Проверить структуры' для просмотра сводки.")
                else:
                    st.json(st.session_state.seed_check_info)

            with mp_col.popover("Materials Project", use_container_width=False):
                if not st.session_state.get("materials_project_api_key", "").strip():
                    mp_key_input = st.text_input(
                        "API-ключ Materials Project",
                        type="password",
                        key="mp_api_key_input",
                    )
                    if st.button("Сохранить API-ключ", key="mp_save_api_key_btn"):
                        if not mp_key_input.strip():
                            st.warning("API-ключ не может быть пустым.")
                        else:
                            st.session_state.materials_project_api_key = mp_key_input.strip()
                            save_config_state()
                            st.success("API-ключ сохранён в config.json.")
                            st.rerun()
                else:
                    st.success("API-ключ Materials Project найден в config.json.")
                st.text_input("Система (через '-')", key="mp_chemsys")
                st.text_input("Порог энергии выше hull", key="mp_ehull_max")
                if st.button("Добавить в Seeds", key="mp_fetch_btn", type="primary"):
                    ok, msg, group = fetch_mp_seed_group(
                        st.session_state.get("materials_project_api_key", ""),
                        st.session_state.get("mp_chemsys", ""),
                        st.session_state.get("mp_ehull_max", ""),
                        st.session_state.seed_next_group_id,
                    )
                    if ok:
                        st.session_state.seed_next_group_id += 1
                        st.session_state.seed_groups.append(group)
                        st.session_state.seed_check_info = group.get("stats")
                        st.session_state.seed_force_enable = True
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            if st.session_state.seed_existing_candidates:
                toast_tag = f"{workdir_abs}:{len(st.session_state.seed_existing_candidates)}"
                if st.session_state.seed_candidates_toast_tag != toast_tag:
                    st.toast("Найдены Seeds в workdir/Seeds", icon="⚠️")
                    st.session_state.seed_candidates_toast_tag = toast_tag

                with st.popover("⚠️ Найдены Seeds в workdir/Seeds", use_container_width=True):
                    for candidate in list(st.session_state.seed_existing_candidates):
                        gid = candidate["id"]
                        summary = seed_group_summary(candidate)
                        c1, c2, c3 = st.columns([5, 1.4, 2])
                        c1.caption(os.path.basename(candidate["path"]))
                        c1.write(summary)
                        if c2.button("Добавить", key=f"seed_take_existing_{gid}"):
                            st.session_state.seed_groups.append(candidate)
                            st.session_state.seed_existing_candidates = [
                                item for item in st.session_state.seed_existing_candidates if item["id"] != gid
                            ]
                            st.rerun()
                        if c3.button("Не добавлять", key=f"seed_skip_existing_{gid}"):
                            stats = candidate.get("stats", {})
                            elements = stats.get("Элементы", []) if isinstance(stats, dict) else []
                            count = int(stats.get("Количество структур", 0)) if isinstance(stats, dict) else 0
                            new_name = _next_archive_name(seeds_dir, elements if isinstance(elements, list) else [], count)
                            try:
                                os.rename(candidate["path"], new_name)
                            except Exception as exc:
                                st.error(f"Не удалось переименовать файл: {exc}")
                            st.session_state.seed_existing_candidates = [
                                item for item in st.session_state.seed_existing_candidates if item["id"] != gid
                            ]
                            st.rerun()

            for group in list(st.session_state.seed_groups):
                gid = group["id"]
                row_left, row_vis, row_del = st.columns([8, 1, 1])
                with row_left:
                    exp = st.expander(seed_group_summary(group), expanded=False)
                if row_vis.button("🖼️", key=f"seed_vis_group_btn_{gid}", type="secondary"):
                    structures = group.get("structures", [])
                    block_text = "\n".join(
                        str(item.get("structure", "")).rstrip()
                        for item in structures
                        if str(item.get("structure", "")).strip()
                    )
                    ok, msg = launch_stmng_visualizer_for_seed_text(
                        workdir_abs,
                        block_text,
                        f"seed_group_{gid}",
                    )
                    st.toast(msg, icon="✅" if ok else "⚠️")
                if row_del.button("❌", key=f"seed_del_group_btn_{gid}", type="secondary"):
                    st.session_state.seed_confirm_delete_group = gid

                if st.session_state.seed_confirm_delete_group == gid:
                    q1, q2, _ = st.columns([2, 2, 6])
                    q1.warning("Вы уверены, что хотите удалить группу структур?")
                    if q1.button("Да", key=f"seed_del_group_yes_{gid}"):
                        st.session_state.seed_groups = [g for g in st.session_state.seed_groups if g["id"] != gid]
                        st.session_state.seed_confirm_delete_group = None
                        st.rerun()
                    if q2.button("Нет", key=f"seed_del_group_no_{gid}"):
                        st.session_state.seed_confirm_delete_group = None
                        st.rerun()

                with exp:
                    st.caption(group.get("path", ""))
                    for s_idx, item in enumerate(list(group.get("structures", []))):
                        if isinstance(item.get("energy"), float) and math.isnan(item["energy"]):
                            energy_text = "nan"
                        else:
                            energy_text = str(item.get("energy"))
                        meta = (
                            f"№ {item.get('номер')} | {item.get('формула')} | Gen={item.get('Gen')} | "
                            f"generation={item.get('generation')} | number={item.get('number')} | energy={energy_text}"
                        )
                        s_left, s_vis, s_del = st.columns([11, 1, 1])
                        s_left.write(meta)
                        if s_vis.button("🖼️", key=f"seed_vis_struct_btn_{gid}_{s_idx}", type="secondary"):
                            ok, msg = launch_stmng_visualizer_for_seed_text(
                                workdir_abs,
                                str(item.get("structure", "")),
                                f"seed_struct_{gid}_{s_idx}",
                            )
                            st.toast(msg, icon="✅" if ok else "⚠️")
                        if s_del.button("❌", key=f"seed_del_struct_btn_{gid}_{s_idx}"):
                            st.session_state.seed_confirm_delete_structure = f"{gid}:{s_idx}"

                        if st.session_state.seed_confirm_delete_structure == f"{gid}:{s_idx}":
                            c_yes, c_no, _ = st.columns([2, 2, 8])
                            c_yes.warning("Вы уверены, что хотите удалить структуру?")
                            if c_yes.button("Да", key=f"seed_del_struct_yes_{gid}_{s_idx}"):
                                updated_groups = []
                                for g in st.session_state.seed_groups:
                                    if g["id"] != gid:
                                        updated_groups.append(g)
                                        continue
                                    new_structs = [x for j, x in enumerate(g.get("structures", [])) if j != s_idx]
                                    g = dict(g)
                                    g["structures"] = new_structs
                                    if new_structs:
                                        updated_groups.append(g)
                                st.session_state.seed_groups = updated_groups
                                st.session_state.seed_confirm_delete_structure = None
                                st.rerun()
                            if c_no.button("Нет", key=f"seed_del_struct_no_{gid}_{s_idx}"):
                                st.session_state.seed_confirm_delete_structure = None
                                st.rerun()

                        with st.expander("Структура", expanded=False):
                            st.code(item.get("structure", ""), language="text")

    st.markdown(f"### {t('run')}")
    st.markdown("<div class='sticky-panel'>", unsafe_allow_html=True)
    run_col, stop_col = st.columns([1, 1])
    run_clicked = run_col.button(t("run"), disabled=st.session_state.running, use_container_width=True, type="primary")
    stop_clicked = stop_col.button(
        t("stop_label"),
        disabled=not st.session_state.running,
        use_container_width=True,
        type="primary",
        help=t("stop_help"),
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if run_clicked:
        st.session_state.error = ""
        try:
            if st.session_state.get("seeds_enabled", False):
                if not workdir.strip() or not os.path.isdir(workdir.strip()):
                    raise ValueError("Сначала укажите корректную рабочую папку для Seeds.")
                total_seed_structs = sum(len(group.get("structures", [])) for group in st.session_state.get("seed_groups", []))
                seeds_dir = os.path.join(workdir.strip(), "Seeds")
                existing_poscars_path = os.path.join(seeds_dir, "POSCARS")
                has_existing_poscars = os.path.isfile(existing_poscars_path)
                if total_seed_structs <= 0 and not has_existing_poscars:
                    raise ValueError("Seeds включены, но структуры не добавлены.")
                ensure_seeds_export(workdir.strip(), st.session_state.get("seed_groups", []))
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
            save_config_state()
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
    stage = status.get('stage') 
    if not stage or stage == "idle":
        stage_display = "—"
    else:
        stage_display = stage
    st.markdown(
        f"{t('generation')}: {status.get('generation') or '—'} | "
        f"{t('stage')}: {stage_display} | "
        f"{t('done')}: {status.get('done_steps') or 0} | "
        f"{t('total')}: {status.get('total_steps') or 0} | "
        f"{t('gen_size')}: {status.get('gen_size') or '—'}"
    )

    st.markdown(f"### {t('log')}")
    st.text_area(
        t("log"),
        value="\n".join(st.session_state.log_lines[-LOG_MAX_LINES:]),
        height=240,
    )



    ###############################################################################################################################################################

    # CSS для горизонтальной прокрутки и стилизации кнопок (включая Popover)
    st.markdown("""
    <style>
        /* Настраиваем контейнер колонок для горизонтальной прокрутки */
        [data-testid="stHorizontalBlock"] {
            overflow-x: auto;
            flex-wrap: nowrap !important;
            gap: 2px !important; 
            padding-bottom: 15px; 
            scrollbar-width: thin; 
        }
        
        [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
            height: 8px;
        }
        [data-testid="stHorizontalBlock"]::-webkit-scrollbar-track {
            background: #f1f1f1; 
            border-radius: 4px;
        }
        [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
            background: #888; 
            border-radius: 4px;
        }
        
        /* Отключаем растягивание колонок */
        [data-testid="stHorizontalBlock"] > div {
            width: auto !important;
            min-width: fit-content !important;
            flex: 0 0 auto !important;
        }
        
        /* Стилизуем обычные кнопки и кнопку Popover */
        button[kind="secondary"], [data-testid="stPopover"] > button {
            white-space: nowrap !important; 
            height: 45px !important;       
            padding: 0 15px !important;    
            border-radius: 5px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Инициализация переменных
    if "folders" not in st.session_state:
        st.session_state.folders = []
    if "active_folder" not in st.session_state:
        st.session_state.active_folder = None
    if "browser_root" not in st.session_state:
        st.session_state.browser_root = ""
    if "browser_current" not in st.session_state:
        st.session_state.browser_current = ""
    if "results_view_mode" not in st.session_state:
        st.session_state.results_view_mode = "folder"
    if "preview_open_outputs" not in st.session_state:
        st.session_state.preview_open_outputs = {}
    
    st.title(f"{t('view_preview_results_header')}")
    # Списки кнопок без "+" (его мы добавим отдельно как Popover)
    button_names = [f"{t('view_preview_results')}", f"{t('view_all_jobs')}"] + st.session_state.folders

    # Создаем колонки: количество папок + 1 для кнопки "+"
    cols = st.columns(len(button_names) + 1)

    # Отрисовываем кнопки папок
    for i, btn_name in enumerate(button_names):
        with cols[i]:
            if i == 0:
                if st.button(btn_name, key=f"btn_static_{i}"):
                    st.session_state.results_view_mode = "preview"
            elif i == 1:
                if st.button(btn_name, key=f"btn_static_{i}"):
                    workdir = st.session_state.get("workdir", "").strip()
                    st.session_state.results_view_mode = "folder"
                    if os.path.isdir(workdir):
                        st.session_state.active_folder = workdir
                        st.session_state.browser_root = workdir
                        st.session_state.browser_current = workdir
                    else:
                        st.warning(t("folder_does_not_exist"))
            else:
                folder_display_name = os.path.basename(btn_name) or btn_name
                if st.button(f"📁 {folder_display_name}", key=f"btn_folder_{btn_name}"):
                    st.session_state.results_view_mode = "folder"
                    st.session_state.active_folder = btn_name
                    st.session_state.browser_root = btn_name
                    st.session_state.browser_current = btn_name

    # Отрисовываем кнопку "+" в последней колонке
    with cols[-1]:
        # Используем Popover (всплывающее окно) вместо Tkinter
        with st.popover("➕", use_container_width=False):
            st.write(t("choose_directory"))
            new_folder = st.text_input(t("insert_local_path"), placeholder=t("example_path"))
            
            if st.button(t("add_folder"), type="primary"):
                if not new_folder:
                    st.warning(t("path_cannot_be_empty"))
                elif not os.path.isdir(new_folder):
                    st.error(t("folder_does_not_exist"))
                elif new_folder in st.session_state.folders:
                    st.warning(t("folder_already_added"))
                else:
                    st.session_state.folders.append(new_folder)
                    st.rerun() # Перезагружаем интерфейс для отображения новой кнопки

    st.divider()

    if st.session_state.results_view_mode == "preview":
        render_preview_results_panel()
    elif st.session_state.browser_root:
        render_folder_browser(st.session_state.browser_root, st.session_state.browser_current)
    else:
        st.info(t("select_added_folder_to_view_contents"))
    



    if st.session_state.running:
        time.sleep(0.5)
        st.rerun()


if __name__ == "__main__":
    main()
