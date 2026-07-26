import ctypes
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from app import logic


def _runtime_root_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _config_dir() -> str:
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return os.path.join(appdata, "USPEX Runner")
    return _runtime_root_dir()


def _default_workdir() -> str:
    install_dir = os.environ.get("USPEX_INSTALL_DIR", "").strip()
    if install_dir:
        primary = os.path.join(install_dir, "projects")
    else:
        primary = os.path.join(_config_dir(), "projects")
    os.makedirs(primary, exist_ok=True)
    return primary


RUNTIME_ROOT = _runtime_root_dir()
APP_DIR = os.path.join(RUNTIME_ROOT, "app")
CONFIG_PATH = os.path.join(_config_dir(), "config.json")
LOG_MAX_LINES = 1500
DEFAULT_ELEMENTS_TEXT = "Si O"
DEFAULT_COUNTS_TEXT = "6 12"
DEFAULT_RATIOS_TEXT = "1 2"
DEFAULT_MIN_AT_TEXT = "8"
DEFAULT_MAX_AT_TEXT = "18"
DEFAULT_ADVANCED_PARAMS = {
    "calculationMethod": "",
    "calculationType": "",
    "optType": "",
    "atomType": "",
    "numSpecies": "",
    "ExternalPressure": "",
    "valences": "",
    "goodBonds": "",
    "checkConnectivity": "",
    "fitLimit": "",
    "populationSize": "80",
    "initialPopSize": "200",
    "numGenerations": "60",
    "stopCrit": "20",
    "bestFrac": "",
    "keepBestHM": "",
    "reoptOld": "",
    "symmetries": "",
    "splitInto": "",
    "fracGene": "",
    "fracRand": "",
    "fracTopRand": "",
    "fracPerm": "",
    "fracAtomsMut": "",
    "fracPyXTal": "",
    "howManySwaps": "",
    "specificSwaps": "",
    "AutoFrac": "",
    "minVectorLength": "",
    "IonDistances": "",
    "constraintEnhancement": "",
    "Latticevalues": "",
    "abinitioCode": "",
    "KresolStart": "",
    "vacuumSize": "",
    "numParallelCalcs": "",
    "commandExecutable": "",
    "whichCluster": "",
    "remoteFolder": "",
    "PhaseDiagram": "",
    "coresPerJob": "",
    "sleepSeconds": "",
    "pickUpGen": "",
    "pickUpFolder": "",
    "RmaxFing": "",
    "deltaFing": "",
    "sigmaFing": "",
    "doSpaceGroup": "",
    "SymTolerance": "",
    "firstGeneMax": "",
    "fracTrans": "",
    "howManyTrans": "",
    "mutationRate": "",
    "mutationDegree": "",
    "orderingActive": "",
    "symmetrize": "",
    "valenceElectr": "",
    "percSliceShift": "",
    "maxDistHeredity": "",
    "manyParents": "",
    "minSlice": "",
    "maxSlice": "",
    "repeatForStatistics": "",
    "stopFitness": "",
    "fixRndSeed": "",
    "collectForces": "",
}
MODE_KEYS = ("fixed", "single", "variable")

STMNG_EXE_PATH = r"C:\Program Files\STMng\STMng.exe"
STMNG_WORKDIR = r"C:\Program Files\STMng"
STMNG_TEMPLATE_PATH = os.path.join(APP_DIR, "test.stm")
STMNG_XYZ_TEMPLATE_PATH = os.path.join(APP_DIR, "xyz_test.stm")
STRUCTURE_COLLECTION_DIR = os.path.join(RUNTIME_ROOT, "webapp", "StructureCollection")
CRYSTAL_VAULT_SITE_DIR = os.path.join(RUNTIME_ROOT, "webapp", "StructureCollection", "site")


def _default_specific_files() -> list[dict[str, str]]:
    return [
        {
            "name": "input_ase_1.yaml",
            "content": 'fmax: 0.1\noptimizer_name: "LBFGS"\nmax_step: 500\n',
        },
        {
            "name": "input_ase_2.yaml",
            "content": 'fmax: 0.02\noptimizer_name: "LBFGS"\nmax_step: 1000\nfilter_name: FrechetCellFilter\n',
        },
        {
            "name": "input_ase_3.yaml",
            "content": 'fmax: 0.002\noptimizer_name: "LBFGS"\nmax_step: 1000\nfilter_name: FrechetCellFilter\n',
        },
    ]


def _sanitize_specific_filename(name: str) -> str:
    cleaned = str(name or "").strip().replace("\\", "_").replace("/", "_")
    if not cleaned:
        return ""
    return os.path.basename(cleaned)


def _sanitize_specific_files(value: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _sanitize_specific_filename(str(item.get("name", "")))
        if not name:
            continue
        content = str(item.get("content", ""))
        out.append({"name": name, "content": content})
    return out


def _specific_files_from_workdir(workdir: str) -> list[dict[str, str]]:
    specific_dir = os.path.join(workdir, "Specific")
    if not os.path.isdir(specific_dir):
        return []
    files: list[dict[str, str]] = []
    for name in sorted(os.listdir(specific_dir), key=lambda s: s.lower()):
        path = os.path.join(specific_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue
        files.append({"name": name, "content": content})
    return files


def ensure_specific_export(workdir: str, files: list[dict[str, str]]) -> str:
    if not workdir:
        raise ValueError("Workdir is required for Specific export.")
    specific_dir = os.path.join(workdir, "Specific")
    os.makedirs(specific_dir, exist_ok=True)
    for item in _sanitize_specific_files(files):
        name = _sanitize_specific_filename(item.get("name", ""))
        if not name:
            continue
        path = os.path.join(specific_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(str(item.get("content", "")))
    return specific_dir


def _bundled_uspex_exe_path() -> str:
    candidate = os.path.abspath(os.path.join(RUNTIME_ROOT, "uspex.exe"))
    if os.path.isfile(candidate):
        return candidate
    return ""


def _default_uspex_exe_path() -> str:
    bundled = _bundled_uspex_exe_path()
    if bundled:
        return bundled
    return logic.DEFAULT_USPEX_EXE


_COMMENT_RE = re.compile(
    r"Gen\s*=\s*(?P<Gen>[-+]?\d+)\s*,\s*"
    r"generation\s*=\s*(?P<generation>[-+]?\d+)\s*,\s*"
    r"number\s*=\s*(?P<number>[-+]?\d+)\s*,\s*"
    r"energy\s*=\s*(?P<energy>[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)"
)


def load_config() -> dict[str, Any]:
    if not os.path.isfile(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _formula(elements: list[str], counts: list[int]) -> str:
    return " ".join(f"{el}{c if c != 1 else ''}" for el, c in zip(elements, counts))


def check_structures(poscar_path: str) -> dict[str, object]:
    try:
        with open(poscar_path, "r", encoding="utf-8", errors="replace") as file_obj:
            lines = [line.rstrip("\n") for line in file_obj]
    except Exception as exc:
        raise ValueError(f"Cannot open file: {exc}") from exc

    i = 0
    n = len(lines)
    structures_count = 0
    all_elements: set[str] = set()
    systems: set[tuple[str, ...]] = set()

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
            raise ValueError("Invalid POSCAR/POSCARS: bad scale factor.") from exc

        i = skip_empty(i + 1)
        if i + 2 >= n:
            raise ValueError("Invalid POSCAR/POSCARS: missing lattice vectors.")
        i = skip_empty(i + 3)
        if i >= n:
            raise ValueError("Invalid POSCAR/POSCARS: missing element symbols line (VASP-5).")

        elem_symbols = lines[i].split()
        if not elem_symbols or not any(any(ch.isalpha() for ch in token) for token in elem_symbols):
            raise ValueError("Only VASP-5 format is supported (element symbols line required).")
        i = skip_empty(i + 1)
        if i >= n:
            raise ValueError("Invalid POSCAR/POSCARS: missing atom counts line.")
        try:
            counts = [int(x) for x in lines[i].split()]
        except Exception as exc:
            raise ValueError("Invalid POSCAR/POSCARS: atom counts must be integers.") from exc
        if len(counts) != len(elem_symbols):
            raise ValueError("Invalid POSCAR/POSCARS: elements/counts length mismatch.")
        if any(x <= 0 for x in counts):
            raise ValueError("Invalid POSCAR/POSCARS: atom counts must be > 0.")
        i += 1

        i = skip_empty(i)
        if i >= n:
            raise ValueError("Invalid POSCAR/POSCARS: missing coordinate mode.")
        if lines[i].lower().startswith("s"):
            i = skip_empty(i + 1)
            if i >= n:
                raise ValueError("Invalid POSCAR/POSCARS: missing coordinate mode after selective dynamics.")
        if not lines[i].lower().startswith(("d", "c")):
            raise ValueError("Invalid POSCAR/POSCARS: mode must start with Direct or Cartesian.")

        i = skip_empty(i + 1)
        total_atoms = sum(counts)
        if i + total_atoms > n:
            raise ValueError("Invalid POSCAR/POSCARS: not enough coordinate rows.")
        i += total_atoms

        structures_count += 1
        elems_set = set(elem_symbols)
        all_elements |= elems_set
        systems.add(tuple(sorted(elems_set)))
        i = skip_empty(i)

    if structures_count <= 0:
        raise ValueError("No valid POSCAR structures found.")
    return {
        "count": structures_count,
        "elements": sorted(all_elements),
        "systems": ["-".join(sys_items) for sys_items in sorted(systems)],
    }


def parse_poscars(path: str) -> list[dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as file_obj:
            lines = file_obj.read().splitlines()
    except Exception:
        return []

    n = len(lines)
    i = 0
    out: list[dict[str, Any]] = []
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
            gen_val = generation = number = None
            energy = None

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
            idx += 1
            out.append(
                {
                    "index": idx,
                    "formula": _formula(elements, counts),
                    "Gen": gen_val,
                    "generation": generation,
                    "number": number,
                    "energy": energy,
                    "structure": "\n".join(lines[start:end]),
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


def build_seed_group(path: str, group_id: int, source: str) -> dict[str, Any]:
    stats = check_structures(path)
    structures = parse_poscars(path)
    if not structures:
        raise ValueError("Failed to parse POSCAR structures.")
    for item in structures:
        item["seed_generation"] = None
        item["generation_user_set"] = False
    return {
        "id": group_id,
        "path": os.path.abspath(path),
        "source": source,
        "source_label": "",
        "group_generation": None,
        "stats": stats,
        "structures": structures,
    }


def ensure_seed_export(workdir: str, seed_groups: list[dict[str, Any]], folder_name: str, label: str) -> None:
    seeds_dir = os.path.join(workdir, folder_name)
    os.makedirs(seeds_dir, exist_ok=True)

    for name in os.listdir(seeds_dir):
        if re.fullmatch(r"POSCARS(_\d+)?", name):
            try:
                os.remove(os.path.join(seeds_dir, name))
            except Exception:
                pass

    by_generation: dict[int, list[str]] = {}
    missing: list[str] = []
    for group in seed_groups:
        gid = int(group.get("id", -1))
        group_generation = group.get("group_generation")
        structures = list(group.get("structures", []))
        for idx, item in enumerate(structures):
            text = str(item.get("structure", "")).rstrip()
            if not text:
                continue
            seed_generation = item.get("seed_generation")
            target_generation = seed_generation if seed_generation is not None else group_generation
            if target_generation is None:
                missing.append(f"group {gid}, structure #{idx + 1}")
                continue
            gen = int(target_generation)
            by_generation.setdefault(gen, []).append(text)

    if missing:
        msg = ", ".join(missing[:8])
        if len(missing) > 8:
            msg += ", ..."
        raise ValueError(f"Set 'Add to generation' for all {label} before run. Missing: {msg}")

    for gen in sorted(by_generation.keys()):
        out_path = os.path.join(seeds_dir, f"POSCARS_{gen}")
        with open(out_path, "w", encoding="utf-8", newline="\n") as file_obj:
            file_obj.write("\n".join(by_generation[gen]))
            file_obj.write("\n")


def _parse_generation_value(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        gen = int(text)
    except Exception as exc:
        raise ValueError("Generation must be an integer.") from exc
    if gen <= 0:
        raise ValueError("Generation must be >= 1.")
    return gen


def launch_stmng_visualizer(target_path: str, template_path: str) -> tuple[bool, str]:
    def _clean_env_for_external_process() -> dict[str, str]:
        env = dict(os.environ)
        for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONUTF8", "PYTHONNOUSERSITE", "_MEIPASS2"):
            env.pop(key, None)
        path_value = str(env.get("PATH", ""))
        if path_value:
            runtime_root = os.path.abspath(RUNTIME_ROOT).lower()
            parts = []
            for raw in path_value.split(os.pathsep):
                p = raw.strip()
                if not p:
                    continue
                pl = p.lower()
                try:
                    abs_p = os.path.abspath(p).lower()
                except Exception:
                    abs_p = pl
                if runtime_root and abs_p.startswith(runtime_root):
                    continue
                if "uspex runner" in pl and "\\_internal" in pl:
                    continue
                parts.append(p)
            env["PATH"] = os.pathsep.join(parts)
        return env

    exe_path = STATE.stmng_path
    stmng_workdir = os.path.dirname(exe_path) if exe_path else STMNG_WORKDIR
    cmd = [exe_path, "--read", target_path, template_path]
    clean_env = _clean_env_for_external_process()
    debug_tail = (
        f" CMD={cmd}; CWD={stmng_workdir}; "
        f"exists(exe)={os.path.isfile(exe_path)}; "
        f"exists(target)={os.path.isfile(target_path)}; "
        f"exists(template)={os.path.isfile(template_path)}; "
        f"exists(cwd)={os.path.isdir(stmng_workdir)}; "
        f"clean_env=True; PATH_count={len(str(clean_env.get('PATH', '')).split(os.pathsep))}"
    )
    if not os.path.isfile(target_path):
        return False, "Target file not found." + debug_tail
    if not os.path.isfile(exe_path):
        return False, f"STMng not found: {exe_path}." + debug_tail
    if not os.path.isdir(stmng_workdir):
        return False, f"STMng workdir not found: {stmng_workdir}." + debug_tail
    if not os.path.isfile(template_path):
        return False, f"Template not found: {template_path}." + debug_tail
    try:
        # Reset DLL search path to default before launching external Electron app.
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass
        subprocess.Popen(
            cmd,
            cwd=stmng_workdir,
            env=clean_env,
            shell=False,
            close_fds=True,
        )
    except Exception as exc:
        return False, f"Failed to start STMng: {exc}." + debug_tail
    return True, "Visualizer started." + debug_tail


@dataclass
class AppState:
    exe_path: str = field(default_factory=_default_uspex_exe_path)
    stmng_path: str = field(default_factory=lambda: STMNG_EXE_PATH)
    workdir: str = ""
    browser_current_path: str = ""
    mode: str = "fixed"
    elements_text: str = DEFAULT_ELEMENTS_TEXT
    counts_text: str = DEFAULT_COUNTS_TEXT
    ratios_text: str = DEFAULT_RATIOS_TEXT
    min_at_text: str = DEFAULT_MIN_AT_TEXT
    max_at_text: str = DEFAULT_MAX_AT_TEXT
    materials_project_api_key: str = ""
    mp_chemsys: str = ""
    mp_ehull_max: str = "0.05"
    anti_materials_project_api_key: str = ""
    anti_mp_chemsys: str = ""
    anti_mp_ehull_max: str = "0.05"
    seeds_enabled: bool = False
    seed_groups: list[dict[str, Any]] = field(default_factory=list)
    seed_next_group_id: int = 1
    anti_seeds_enabled: bool = False
    anti_seed_groups: list[dict[str, Any]] = field(default_factory=list)
    anti_seed_next_group_id: int = 1
    specific_enabled: bool = False
    specific_files: list[dict[str, str]] = field(default_factory=list)
    preview_text: str = ""
    preview_dirty: bool = False
    advanced_enabled: bool = False
    advanced_params: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ADVANCED_PARAMS))
    mode_state: dict[str, dict[str, Any]] = field(default_factory=dict)

    proc: subprocess.Popen | None = None
    monitor: logic.UspexMonitor = field(default_factory=logic.UspexMonitor)
    log_lines: list[str] = field(default_factory=list)
    status: dict[str, Any] = field(default_factory=lambda: logic.UspexMonitor().to_dict())
    history: list[dict[str, Any]] = field(default_factory=list)
    running: bool = False
    error: str = ""
    log_version: int = 0

    cleanup_paths: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)


STATE = AppState()


def _default_mode_entry() -> dict[str, Any]:
    return {
        "elements_text": DEFAULT_ELEMENTS_TEXT,
        "counts_text": DEFAULT_COUNTS_TEXT,
        "ratios_text": DEFAULT_RATIOS_TEXT,
        "min_at_text": DEFAULT_MIN_AT_TEXT,
        "max_at_text": DEFAULT_MAX_AT_TEXT,
        "advanced_enabled": False,
        "advanced_params": dict(DEFAULT_ADVANCED_PARAMS),
        "preview_text": "",
        "preview_dirty": False,
    }


def _sanitize_mode_state(value: Any) -> dict[str, dict[str, Any]]:
    out = {k: _default_mode_entry() for k in MODE_KEYS}
    if not isinstance(value, dict):
        return out
    for mode in MODE_KEYS:
        src = value.get(mode, {})
        if not isinstance(src, dict):
            continue
        out[mode]["elements_text"] = str(src.get("elements_text", out[mode]["elements_text"]))
        out[mode]["counts_text"] = str(src.get("counts_text", out[mode]["counts_text"]))
        out[mode]["ratios_text"] = str(src.get("ratios_text", out[mode]["ratios_text"]))
        out[mode]["min_at_text"] = str(src.get("min_at_text", out[mode]["min_at_text"]))
        out[mode]["max_at_text"] = str(src.get("max_at_text", out[mode]["max_at_text"]))
        out[mode]["advanced_enabled"] = bool(src.get("advanced_enabled", out[mode]["advanced_enabled"]))
        ap = dict(DEFAULT_ADVANCED_PARAMS)
        if isinstance(src.get("advanced_params"), dict):
            for k in DEFAULT_ADVANCED_PARAMS.keys():
                v = src["advanced_params"].get(k)
                if v is None:
                    continue
                t = str(v).strip()
                if t:
                    ap[k] = t
        out[mode]["advanced_params"] = ap
        out[mode]["preview_text"] = str(src.get("preview_text", "") or "")
        out[mode]["preview_dirty"] = bool(src.get("preview_dirty", False))
    return out


def _expected_preview_for_entry(mode: str, entry: dict[str, Any]) -> str:
    elements_text = str(entry.get("elements_text", DEFAULT_ELEMENTS_TEXT))
    counts_text = str(entry.get("counts_text", DEFAULT_COUNTS_TEXT))
    ratios_text = str(entry.get("ratios_text", DEFAULT_RATIOS_TEXT))
    min_at_text = str(entry.get("min_at_text", DEFAULT_MIN_AT_TEXT))
    max_at_text = str(entry.get("max_at_text", DEFAULT_MAX_AT_TEXT))
    advanced_enabled = bool(entry.get("advanced_enabled", False))
    advanced_params = dict(DEFAULT_ADVANCED_PARAMS)
    if isinstance(entry.get("advanced_params"), dict):
        for k in DEFAULT_ADVANCED_PARAMS.keys():
            v = entry["advanced_params"].get(k)
            if v is None:
                continue
            t = str(v).strip()
            if t:
                advanced_params[k] = t
    if mode == "fixed":
        elements = logic.parse_elements(elements_text)
        counts = logic.parse_int_list(counts_text)
        base = logic.build_input_fixed(elements, counts)
    elif mode == "single":
        elements = logic.parse_elements(elements_text)
        ratios = logic.parse_int_list(ratios_text)
        min_at = int(min_at_text)
        max_at = int(max_at_text)
        base = logic.build_input_single(elements, ratios, min_at, max_at)
    else:
        min_at = int(min_at_text)
        max_at = int(max_at_text)
        base = logic.build_input_variable(elements_text, min_at, max_at)
    return append_advanced_params(base, advanced_params, advanced_enabled)


def _apply_mode_entry(mode: str) -> None:
    entry = dict(STATE.mode_state.get(mode) or _default_mode_entry())
    STATE.elements_text = str(entry.get("elements_text", DEFAULT_ELEMENTS_TEXT))
    STATE.counts_text = str(entry.get("counts_text", DEFAULT_COUNTS_TEXT))
    STATE.ratios_text = str(entry.get("ratios_text", DEFAULT_RATIOS_TEXT))
    STATE.min_at_text = str(entry.get("min_at_text", DEFAULT_MIN_AT_TEXT))
    STATE.max_at_text = str(entry.get("max_at_text", DEFAULT_MAX_AT_TEXT))
    STATE.advanced_enabled = bool(entry.get("advanced_enabled", False))
    ap = dict(DEFAULT_ADVANCED_PARAMS)
    if isinstance(entry.get("advanced_params"), dict):
        for k in DEFAULT_ADVANCED_PARAMS.keys():
            v = entry["advanced_params"].get(k)
            if v is None:
                continue
            t = str(v).strip()
            if t:
                ap[k] = t
    STATE.advanced_params = ap
    try:
        expected = _expected_preview_for_entry(mode, entry)
    except Exception as exc:
        expected = f"(input error: {exc})"
        STATE.error = str(exc)
    preview_text = str(entry.get("preview_text", "") or "")
    if not preview_text:
        preview_text = expected
    preview_dirty = bool(entry.get("preview_dirty", preview_text != expected))
    STATE.preview_text = preview_text
    STATE.preview_dirty = preview_dirty
    entry["preview_text"] = preview_text
    entry["preview_dirty"] = preview_dirty
    STATE.mode_state[mode] = entry


def _config_from_state() -> dict[str, Any]:
    return {
        "exe_path": STATE.exe_path,
        "stmng_path": STATE.stmng_path,
        "workdir": STATE.workdir,
        "browser_current_path": STATE.browser_current_path,
        "mode": STATE.mode,
        "elements_text": STATE.elements_text,
        "counts_text": STATE.counts_text,
        "ratios_text": STATE.ratios_text,
        "min_at_text": STATE.min_at_text,
        "max_at_text": STATE.max_at_text,
        "materials_project_api_key": STATE.materials_project_api_key,
        "mp_chemsys": STATE.mp_chemsys,
        "mp_ehull_max": STATE.mp_ehull_max,
        "anti_materials_project_api_key": STATE.anti_materials_project_api_key,
        "anti_mp_chemsys": STATE.anti_mp_chemsys,
        "anti_mp_ehull_max": STATE.anti_mp_ehull_max,
        "seeds_enabled": STATE.seeds_enabled,
        "anti_seeds_enabled": STATE.anti_seeds_enabled,
        "advanced_enabled": STATE.advanced_enabled,
        "advanced_params": STATE.advanced_params,
        "mode_state": STATE.mode_state,
        "preview_text": STATE.preview_text,
        "preview_dirty": STATE.preview_dirty,
        "seed_groups": STATE.seed_groups,
        "seed_next_group_id": STATE.seed_next_group_id,
        "anti_seed_groups": STATE.anti_seed_groups,
        "anti_seed_next_group_id": STATE.anti_seed_next_group_id,
        "specific_enabled": STATE.specific_enabled,
        "specific_files": STATE.specific_files,
    }


def _apply_loaded_config(config: dict[str, Any]) -> None:
    STATE.exe_path = str(config.get("exe_path") or _default_uspex_exe_path())
    STATE.stmng_path = str(config.get("stmng_path") or STMNG_EXE_PATH)
    STATE.workdir = str(config.get("workdir") or _default_workdir())
    STATE.browser_current_path = str(config.get("browser_current_path") or "")
    STATE.mode = str(config.get("mode") or "fixed")
    if STATE.mode not in MODE_KEYS:
        STATE.mode = "fixed"
    STATE.elements_text = str(config.get("elements_text") or DEFAULT_ELEMENTS_TEXT)
    STATE.counts_text = str(config.get("counts_text") or DEFAULT_COUNTS_TEXT)
    STATE.ratios_text = str(config.get("ratios_text") or DEFAULT_RATIOS_TEXT)
    STATE.min_at_text = str(config.get("min_at_text") or DEFAULT_MIN_AT_TEXT)
    STATE.max_at_text = str(config.get("max_at_text") or DEFAULT_MAX_AT_TEXT)
    STATE.materials_project_api_key = str(config.get("materials_project_api_key") or "")
    STATE.mp_chemsys = str(config.get("mp_chemsys") or "")
    STATE.mp_ehull_max = str(config.get("mp_ehull_max") or "0.05")
    STATE.anti_materials_project_api_key = str(config.get("anti_materials_project_api_key") or "")
    STATE.anti_mp_chemsys = str(config.get("anti_mp_chemsys") or "")
    STATE.anti_mp_ehull_max = str(config.get("anti_mp_ehull_max") or "0.05")
    STATE.seeds_enabled = bool(config.get("seeds_enabled", False))
    STATE.anti_seeds_enabled = bool(config.get("anti_seeds_enabled", False))
    STATE.advanced_enabled = bool(config.get("advanced_enabled", False))
    if isinstance(config.get("seed_groups"), list):
        STATE.seed_groups = list(config.get("seed_groups") or [])
    STATE.seed_next_group_id = int(config.get("seed_next_group_id") or (len(STATE.seed_groups) + 1))
    if isinstance(config.get("anti_seed_groups"), list):
        STATE.anti_seed_groups = list(config.get("anti_seed_groups") or [])
    STATE.anti_seed_next_group_id = int(config.get("anti_seed_next_group_id") or (len(STATE.anti_seed_groups) + 1))
    STATE.specific_enabled = bool(config.get("specific_enabled", False))
    STATE.specific_files = _sanitize_specific_files(config.get("specific_files"))
    merged = dict(DEFAULT_ADVANCED_PARAMS)
    if isinstance(config.get("advanced_params"), dict):
        for key in DEFAULT_ADVANCED_PARAMS.keys():
            value = config["advanced_params"].get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                merged[key] = text
    STATE.advanced_params = merged
    STATE.mode_state = _sanitize_mode_state(config.get("mode_state"))
    # backward-compatible fallback for old config without mode_state
    if not isinstance(config.get("mode_state"), dict):
        STATE.mode_state = {k: _default_mode_entry() for k in MODE_KEYS}
        STATE.mode_state[STATE.mode] = {
            "elements_text": STATE.elements_text,
            "counts_text": STATE.counts_text,
            "ratios_text": STATE.ratios_text,
            "min_at_text": STATE.min_at_text,
            "max_at_text": STATE.max_at_text,
            "advanced_enabled": STATE.advanced_enabled,
            "advanced_params": dict(STATE.advanced_params),
        }
    _apply_mode_entry(STATE.mode)
    try:
        expected = _expected_preview_for_entry(STATE.mode, STATE.mode_state.get(STATE.mode, _default_mode_entry()))
        STATE.error = ""
    except Exception as exc:
        expected = f"(input error: {exc})"
        STATE.error = str(exc)
    cfg_preview = str(config.get("preview_text") or "")
    if cfg_preview:
        STATE.preview_text = cfg_preview
        STATE.preview_dirty = bool(config.get("preview_dirty", cfg_preview != expected))
    else:
        STATE.preview_text = expected
        STATE.preview_dirty = False
    STATE.mode_state[STATE.mode]["preview_text"] = STATE.preview_text
    STATE.mode_state[STATE.mode]["preview_dirty"] = STATE.preview_dirty


def _reset_defaults() -> None:
    STATE.mode = "fixed"
    STATE.elements_text = DEFAULT_ELEMENTS_TEXT
    STATE.counts_text = DEFAULT_COUNTS_TEXT
    STATE.ratios_text = DEFAULT_RATIOS_TEXT
    STATE.min_at_text = DEFAULT_MIN_AT_TEXT
    STATE.max_at_text = DEFAULT_MAX_AT_TEXT
    STATE.advanced_enabled = False
    STATE.advanced_params = dict(DEFAULT_ADVANCED_PARAMS)
    STATE.specific_enabled = False
    STATE.specific_files = []
    STATE.mode_state = {k: _default_mode_entry() for k in MODE_KEYS}
    _apply_mode_entry("fixed")


def append_advanced_params(text: str, params: dict[str, str], enabled: bool) -> str:
    if not enabled:
        return text
    block_end_map = {
        "abinitioCode": "ENDabinit",
        "KresolStart": "Kresolend",
        "vacuumSize": "EndVacuumSize",
        "Latticevalues": "Endvalues",
        "specificSwaps": "EndSpecific",
        "splitInto": "EndSplitInto",
        "symmetries": "EndSymmetries",
        "valences": "EndValences",
        "goodBonds": "EndGoodBonds",
        "IonDistances": "EndDistances",
        "commandExecutable": "EndExecutable",
    }
    lines = []
    for name in DEFAULT_ADVANCED_PARAMS.keys():
        value = str(params.get(name, "")).strip()
        if value:
            if name in block_end_map:
                lines.append("")
                lines.append(f"% {name}")
                lines.append(value)
                lines.append(f"% {block_end_map[name]}")
                lines.append("")
            else:
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


def _build_input_preview() -> str:
    mode = STATE.mode
    if mode == "fixed":
        elements = logic.parse_elements(STATE.elements_text)
        counts = logic.parse_int_list(STATE.counts_text)
        base = logic.build_input_fixed(elements, counts)
        return append_advanced_params(base, STATE.advanced_params, STATE.advanced_enabled)
    if mode == "single":
        elements = logic.parse_elements(STATE.elements_text)
        ratios = logic.parse_int_list(STATE.ratios_text)
        min_at = int(STATE.min_at_text)
        max_at = int(STATE.max_at_text)
        base = logic.build_input_single(elements, ratios, min_at, max_at)
        return append_advanced_params(base, STATE.advanced_params, STATE.advanced_enabled)
    min_at = int(STATE.min_at_text)
    max_at = int(STATE.max_at_text)
    base = logic.build_input_variable(STATE.elements_text, min_at, max_at)
    return append_advanced_params(base, STATE.advanced_params, STATE.advanced_enabled)


def _append_log(line: str) -> None:
    STATE.log_lines.append(line.rstrip("\n"))
    if len(STATE.log_lines) > LOG_MAX_LINES * 2:
        STATE.log_lines = STATE.log_lines[-LOG_MAX_LINES:]
    STATE.log_version += 1


def _reader_loop(proc: subprocess.Popen) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        with STATE.lock:
            _append_log(line)
            info = STATE.monitor.feed_line(line)
            if info:
                STATE.status = info
                STATE.history.append(
                    {
                        "time": time.time(),
                        "done": info.get("done_steps") or 0,
                        "total": info.get("total_steps") or 0,
                    }
                )
    code = proc.wait()
    with STATE.lock:
        _append_log(f"[GUI] USPEX exited (code: {code})")
        STATE.running = False
        STATE.proc = None


def _scan_preview_results(workdir: str) -> dict[str, Any]:
    calculation_dir = os.path.join(workdir or "", "Calculation")
    structures: dict[int, dict[int, dict[str, Any]]] = {}
    if not os.path.isdir(calculation_dir):
        return {"calculation_dir": calculation_dir, "structures": {}}
    for name in os.listdir(calculation_dir):
        m = re.match(r"^Calcfold_(\d+)_(\d+)$", name)
        if not m:
            continue
        n = int(m.group(1))
        stage = int(m.group(2))
        folder = os.path.join(calculation_dir, name)
        out_xyz = os.path.join(folder, "output.xyz")
        if n not in structures:
            structures[n] = {}
        structures[n][stage] = {
            "folder": folder,
            "output_xyz": out_xyz,
            "has_folder": os.path.isdir(folder),
            "has_output": os.path.isfile(out_xyz),
        }
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
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except Exception:
        return False


def _cleanup_files() -> None:
    now = time.time()
    pending = []
    for item in STATE.cleanup_paths:
        path = str(item.get("path", ""))
        delete_after = float(item.get("delete_after", 0.0))
        if not path:
            continue
        if now < delete_after:
            pending.append(item)
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pending.append({"path": path, "delete_after": now + 3.0})
    STATE.cleanup_paths = pending


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(RUNTIME_ROOT, "webapp", "templates"),
        static_folder=os.path.join(RUNTIME_ROOT, "webapp", "static"),
    )

    with STATE.lock:
        loaded_config = load_config()
        _apply_loaded_config(loaded_config)
        if not str(loaded_config.get("exe_path") or "").strip():
            save_config(_config_from_state())
        if not STATE.preview_text:
            try:
                STATE.preview_text = _build_input_preview()
                STATE.preview_dirty = False
            except Exception as exc:
                STATE.preview_text = f"(input error: {exc})"
                STATE.preview_dirty = False
            STATE.mode_state[STATE.mode]["preview_text"] = STATE.preview_text
            STATE.mode_state[STATE.mode]["preview_dirty"] = STATE.preview_dirty

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/StructureCollection/site/")
    def crystal_vault_index():
        if not os.path.isfile(os.path.join(CRYSTAL_VAULT_SITE_DIR, "index.html")):
            return jsonify({"ok": False, "message": "Crystal Vault site not found."}), 404
        return send_from_directory(CRYSTAL_VAULT_SITE_DIR, "index.html")

    @app.get("/StructureCollection/site/<path:filename>")
    def crystal_vault_assets(filename: str):
        safe_path = os.path.abspath(os.path.join(CRYSTAL_VAULT_SITE_DIR, filename))
        if not safe_path.startswith(os.path.abspath(CRYSTAL_VAULT_SITE_DIR)):
            return jsonify({"ok": False, "message": "Invalid path."}), 400
        if not os.path.isfile(safe_path):
            return jsonify({"ok": False, "message": "File not found."}), 404
        return send_from_directory(CRYSTAL_VAULT_SITE_DIR, filename)

    @app.get("/StructureCollection/<path:filename>")
    def crystal_vault_collection_files(filename: str):
        safe_path = os.path.abspath(os.path.join(STRUCTURE_COLLECTION_DIR, filename))
        if not safe_path.startswith(os.path.abspath(STRUCTURE_COLLECTION_DIR)):
            return jsonify({"ok": False, "message": "Invalid path."}), 400
        if not os.path.isfile(safe_path):
            return jsonify({"ok": False, "message": "File not found."}), 404
        return send_from_directory(STRUCTURE_COLLECTION_DIR, filename)

    @app.get("/api/state")
    def api_state():
        with STATE.lock:
            _cleanup_files()
            try:
                expected_preview = _expected_preview_for_entry(
                    STATE.mode,
                    {
                        "elements_text": STATE.elements_text,
                        "counts_text": STATE.counts_text,
                        "ratios_text": STATE.ratios_text,
                        "min_at_text": STATE.min_at_text,
                        "max_at_text": STATE.max_at_text,
                        "advanced_enabled": STATE.advanced_enabled,
                        "advanced_params": STATE.advanced_params,
                    },
                )
            except Exception as exc:
                expected_preview = f"(input error: {exc})"
            return jsonify(
                {
                    "exe_path": STATE.exe_path,
                    "workdir": STATE.workdir,
                    "browser_current_path": STATE.browser_current_path,
                    "mode": STATE.mode,
                    "elements_text": STATE.elements_text,
                    "counts_text": STATE.counts_text,
                    "ratios_text": STATE.ratios_text,
                    "min_at_text": STATE.min_at_text,
                    "max_at_text": STATE.max_at_text,
                    "materials_project_api_key": STATE.materials_project_api_key,
                    "materials_project_api_key_set": bool(STATE.materials_project_api_key.strip()),
                    "mp_chemsys": STATE.mp_chemsys,
                    "mp_ehull_max": STATE.mp_ehull_max,
                    "anti_materials_project_api_key": STATE.anti_materials_project_api_key,
                    "anti_materials_project_api_key_set": bool(STATE.anti_materials_project_api_key.strip()),
                    "anti_mp_chemsys": STATE.anti_mp_chemsys,
                    "anti_mp_ehull_max": STATE.anti_mp_ehull_max,
                    "seeds_enabled": STATE.seeds_enabled,
                    "seed_groups": STATE.seed_groups,
                    "anti_seeds_enabled": STATE.anti_seeds_enabled,
                    "anti_seed_groups": STATE.anti_seed_groups,
                    "specific_enabled": STATE.specific_enabled,
                    "specific_files": STATE.specific_files,
                    "stmng_path": STATE.stmng_path,
                    "stmng_installed": os.path.isfile(STATE.stmng_path),
                    "preview_text": STATE.preview_text,
                    "preview_dirty": STATE.preview_dirty,
                    "expected_preview": expected_preview,
                    "advanced_enabled": STATE.advanced_enabled,
                    "advanced_params": STATE.advanced_params,
                    "mode_state": STATE.mode_state,
                    "running": STATE.running,
                    "status": STATE.status,
                    "error": STATE.error,
                    "log_version": STATE.log_version,
                    "preview_results": _scan_preview_results(STATE.workdir.strip()),
                }
            )

    @app.post("/api/settings")
    def api_settings():
        payload = request.get_json(force=True)
        with STATE.lock:
            if isinstance(payload.get("mode_state"), dict):
                STATE.mode_state = _sanitize_mode_state(payload["mode_state"])
            for key in (
                "exe_path",
                "stmng_path",
                "workdir",
                "browser_current_path",
                "mode",
                "elements_text",
                "counts_text",
                "ratios_text",
                "min_at_text",
                "max_at_text",
                "mp_chemsys",
                "mp_ehull_max",
                "anti_mp_chemsys",
                "anti_mp_ehull_max",
            ):
                if key in payload:
                    setattr(STATE, key, str(payload[key]))
            if STATE.mode not in MODE_KEYS:
                STATE.mode = "fixed"
            # If mode_state was sent, use it as source of truth for mode params.
            if isinstance(payload.get("mode_state"), dict):
                _apply_mode_entry(STATE.mode)
            if "materials_project_api_key" in payload:
                STATE.materials_project_api_key = str(payload["materials_project_api_key"])
            if "anti_materials_project_api_key" in payload:
                STATE.anti_materials_project_api_key = str(payload["anti_materials_project_api_key"])
            if "seeds_enabled" in payload:
                STATE.seeds_enabled = bool(payload["seeds_enabled"])
            if "anti_seeds_enabled" in payload:
                STATE.anti_seeds_enabled = bool(payload["anti_seeds_enabled"])
            if "specific_enabled" in payload:
                STATE.specific_enabled = bool(payload["specific_enabled"])
            if "specific_files" in payload:
                STATE.specific_files = _sanitize_specific_files(payload.get("specific_files"))
            if "advanced_enabled" in payload:
                STATE.advanced_enabled = bool(payload["advanced_enabled"])
            if isinstance(payload.get("advanced_params"), dict):
                merged = dict(DEFAULT_ADVANCED_PARAMS)
                for key in DEFAULT_ADVANCED_PARAMS.keys():
                    value = payload["advanced_params"].get(key)
                    if value is None:
                        continue
                    text = str(value).strip()
                    if text:
                        merged[key] = text
                STATE.advanced_params = merged
            STATE.mode_state[STATE.mode] = {
                "elements_text": STATE.elements_text,
                "counts_text": STATE.counts_text,
                "ratios_text": STATE.ratios_text,
                "min_at_text": STATE.min_at_text,
                "max_at_text": STATE.max_at_text,
                "advanced_enabled": STATE.advanced_enabled,
                "advanced_params": dict(STATE.advanced_params),
                "preview_text": str(STATE.mode_state.get(STATE.mode, {}).get("preview_text", "")),
                "preview_dirty": bool(STATE.mode_state.get(STATE.mode, {}).get("preview_dirty", False)),
            }
            try:
                expected_preview = _build_input_preview()
                incoming_preview = payload.get("preview_text")
                force_preview_from_params = bool(payload.get("force_preview_from_params", False))
                if force_preview_from_params:
                    STATE.preview_text = expected_preview
                    STATE.preview_dirty = False
                elif incoming_preview is not None:
                    STATE.preview_text = str(incoming_preview)
                    STATE.preview_dirty = STATE.preview_text != expected_preview
                else:
                    if not STATE.preview_dirty:
                        STATE.preview_text = expected_preview
                    STATE.preview_dirty = STATE.preview_text != expected_preview
                STATE.error = ""
            except Exception as exc:
                STATE.error = str(exc)
                STATE.preview_text = f"(input error: {exc})"
                STATE.preview_dirty = False
            STATE.mode_state[STATE.mode]["preview_text"] = STATE.preview_text
            STATE.mode_state[STATE.mode]["preview_dirty"] = STATE.preview_dirty
            save_config(_config_from_state())
            return jsonify({"ok": True, "preview_text": STATE.preview_text, "preview_dirty": STATE.preview_dirty})

    @app.post("/api/reset-defaults")
    def api_reset_defaults():
        with STATE.lock:
            _reset_defaults()
            try:
                STATE.preview_text = _build_input_preview()
                STATE.preview_dirty = False
                STATE.error = ""
            except Exception as exc:
                STATE.error = str(exc)
                STATE.preview_text = f"(input error: {exc})"
                STATE.preview_dirty = False
            STATE.mode_state[STATE.mode]["preview_text"] = STATE.preview_text
            STATE.mode_state[STATE.mode]["preview_dirty"] = STATE.preview_dirty
            save_config(_config_from_state())
            return jsonify({"ok": True})

    @app.post("/api/specific/workdir-files")
    def api_specific_workdir_files():
        payload = request.get_json(force=True)
        workdir = str(payload.get("workdir", "")).strip()
        if not workdir:
            return jsonify({"ok": True, "exists": False, "files": []})
        if not os.path.isdir(workdir):
            return jsonify({"ok": False, "message": "Workdir does not exist."}), 400
        files = _specific_files_from_workdir(workdir)
        return jsonify({"ok": True, "exists": bool(files), "files": files})

    @app.post("/api/specific/defaults")
    def api_specific_defaults():
        payload = request.get_json(force=True) if request.data else {}
        mode = str(payload.get("mode", "add")).strip().lower()
        defaults = _default_specific_files()
        with STATE.lock:
            if mode == "replace":
                STATE.specific_files = defaults
            else:
                existing_names = {str(x.get("name", "")).lower() for x in STATE.specific_files}
                for item in defaults:
                    n = str(item.get("name", "")).lower()
                    if n in existing_names:
                        continue
                    STATE.specific_files.append(item)
            save_config(_config_from_state())
            return jsonify({"ok": True, "files": STATE.specific_files})

    @app.post("/api/specific/load-from-workdir")
    def api_specific_load_from_workdir():
        payload = request.get_json(force=True)
        workdir = str(payload.get("workdir", "")).strip()
        mode = str(payload.get("mode", "replace")).strip().lower()
        if not workdir or not os.path.isdir(workdir):
            return jsonify({"ok": False, "message": "Valid workdir is required."}), 400
        files = _specific_files_from_workdir(workdir)
        if not files:
            return jsonify({"ok": False, "message": "Specific folder is empty or missing."}), 404
        with STATE.lock:
            if mode == "add":
                existing_names = {str(x.get("name", "")).lower() for x in STATE.specific_files}
                for item in files:
                    n = str(item.get("name", "")).lower()
                    if n in existing_names:
                        continue
                    STATE.specific_files.append(item)
            else:
                STATE.specific_files = files
            save_config(_config_from_state())
            return jsonify({"ok": True, "files": STATE.specific_files})

    @app.post("/api/seeds/check")
    def api_seeds_check():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        if not path:
            return jsonify({"ok": False, "message": "Path is required."}), 400
        try:
            info = check_structures(path)
            return jsonify({"ok": True, "info": info})
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/seeds/add-path")
    def api_seed_add_path():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        if not path:
            return jsonify({"ok": False, "message": "Path is required."}), 400
        with STATE.lock:
            try:
                group = build_seed_group(path, STATE.seed_next_group_id, "manual")
            except Exception as exc:
                return jsonify({"ok": False, "message": str(exc)}), 400
            STATE.seed_next_group_id += 1
            STATE.seed_groups.append(group)
            STATE.seeds_enabled = True
            save_config(_config_from_state())
            return jsonify({"ok": True, "message": "Seed file added."})

    @app.post("/api/seeds/add-mp")
    def api_seed_add_mp():
        payload = request.get_json(force=True)
        api_key = str(payload.get("api_key", "")).strip() or STATE.materials_project_api_key.strip()
        chemsys = str(payload.get("chemsys", "")).strip()
        ehull_text = str(payload.get("ehull", "")).strip()
        if not api_key:
            return jsonify({"ok": False, "message": "Materials Project API key is required."}), 400
        if not chemsys or "-" not in chemsys:
            return jsonify({"ok": False, "message": "chemsys must look like Fe-O."}), 400
        try:
            ehull = float(ehull_text)
            if ehull < 0:
                raise ValueError
        except Exception:
            return jsonify({"ok": False, "message": "Invalid e_above_hull value."}), 400
        try:
            from mp_api.client import MPRester
            from pymatgen.io.vasp import Poscar
        except Exception as exc:
            return jsonify({"ok": False, "message": f"mp_api/pymatgen missing: {exc}"}), 400

        try:
            with MPRester(api_key) as mpr:
                search_fn = mpr.materials.summary.search
                docs = None
                last_exc = None
                for arg_name in ("energy_above_hull", "e_above_hull"):
                    kwargs = {
                        "chemsys": chemsys,
                        "fields": ["material_id", "structure"],
                        "chunk_size": 50,
                        arg_name: (0, ehull),
                    }
                    try:
                        docs = search_fn(**kwargs)
                        break
                    except TypeError as exc:
                        last_exc = exc
                        continue
                    except Exception as exc:
                        msg = str(exc)
                        if "unknown to" in msg and arg_name in msg:
                            last_exc = exc
                            continue
                        raise
                if docs is None:
                    raise last_exc or RuntimeError("No compatible hull argument found.")
        except Exception as exc:
            return jsonify({"ok": False, "message": f"Materials Project request error: {exc}"}), 400
        if not docs:
            return jsonify({"ok": False, "message": "No structures found."}), 404

        structures = []
        all_elements: set[str] = set()
        systems: set[tuple[str, ...]] = set()
        for idx, doc in enumerate(docs, start=1):
            poscar = Poscar(doc.structure)
            elements = [str(x) for x in poscar.site_symbols]
            counts = [int(x) for x in poscar.natoms]
            structures.append(
                {
                    "index": idx,
                    "formula": _formula(elements, counts),
                    "Gen": None,
                    "generation": None,
                    "number": None,
                    "energy": None,
                    "structure": poscar.get_str().rstrip(),
                    "seed_generation": None,
                    "generation_user_set": False,
                }
            )
            elem_set = set(elements)
            all_elements |= elem_set
            systems.add(tuple(sorted(elem_set)))

        with STATE.lock:
            group = {
                "id": STATE.seed_next_group_id,
                "path": f"Materials Project ({chemsys})",
                "source": "mp",
                "source_label": f"mp < Energy Above Hull ({ehull_text})",
                "group_generation": None,
                "stats": {
                    "count": len(structures),
                    "elements": sorted(all_elements),
                    "systems": ["-".join(x) for x in sorted(systems)],
                },
                "structures": structures,
            }
            STATE.seed_next_group_id += 1
            STATE.seed_groups.append(group)
            STATE.seeds_enabled = True
            STATE.materials_project_api_key = api_key
            STATE.mp_chemsys = chemsys
            STATE.mp_ehull_max = ehull_text
            save_config(_config_from_state())
            return jsonify({"ok": True, "message": f"Added {len(structures)} structures from MP."})

    @app.post("/api/seeds/delete-group")
    def api_seed_delete_group():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        with STATE.lock:
            before = len(STATE.seed_groups)
            STATE.seed_groups = [g for g in STATE.seed_groups if int(g.get("id", -1)) != gid]
            if len(STATE.seed_groups) == before:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            save_config(_config_from_state())
            return jsonify({"ok": True})

    @app.post("/api/seeds/set-group-generation")
    def api_seed_set_group_generation():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        try:
            generation = _parse_generation_value(payload.get("generation"))
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        with STATE.lock:
            group = next((g for g in STATE.seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            group["group_generation"] = generation
            for item in group.get("structures", []):
                if not bool(item.get("generation_user_set", False)):
                    item["seed_generation"] = generation
            save_config(_config_from_state())
        return jsonify({"ok": True})

    @app.post("/api/seeds/set-structure-generation")
    def api_seed_set_structure_generation():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        idx = int(payload.get("index", -1))
        try:
            generation = _parse_generation_value(payload.get("generation"))
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        with STATE.lock:
            group = next((g for g in STATE.seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            items = list(group.get("structures", []))
            if idx < 0 or idx >= len(items):
                return jsonify({"ok": False, "message": "Structure not found."}), 404
            item = items[idx]
            if generation is None:
                item["generation_user_set"] = False
                item["seed_generation"] = group.get("group_generation")
            else:
                item["generation_user_set"] = True
                item["seed_generation"] = generation
            save_config(_config_from_state())
        return jsonify({"ok": True})

    @app.post("/api/seeds/reset-group-generations")
    def api_seed_reset_group_generations():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        with STATE.lock:
            group = next((g for g in STATE.seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            group["group_generation"] = None
            for item in group.get("structures", []):
                item["generation_user_set"] = False
                item["seed_generation"] = None
            save_config(_config_from_state())
        return jsonify({"ok": True})

    @app.post("/api/seeds/delete-structure")
    def api_seed_delete_structure():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        idx = int(payload.get("index", -1))
        with STATE.lock:
            updated = []
            removed = False
            for g in STATE.seed_groups:
                if int(g.get("id", -1)) != gid:
                    updated.append(g)
                    continue
                structures = [x for j, x in enumerate(g.get("structures", [])) if j != idx]
                if len(structures) != len(g.get("structures", [])):
                    removed = True
                if structures:
                    ng = dict(g)
                    ng["structures"] = structures
                    ng["stats"] = dict(ng.get("stats", {}))
                    ng["stats"]["count"] = len(structures)
                    updated.append(ng)
            STATE.seed_groups = updated
            if not removed:
                return jsonify({"ok": False, "message": "Structure not found."}), 404
            save_config(_config_from_state())
            return jsonify({"ok": True})

    @app.post("/api/seeds/visualize-group")
    def api_seed_visualize_group():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        with STATE.lock:
            group = next((g for g in STATE.seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            workdir = STATE.workdir.strip()
        if not workdir or not os.path.isdir(workdir):
            return jsonify({"ok": False, "message": "Valid workdir is required."}), 400
        text = "\n".join(
            str(item.get("structure", "")).rstrip()
            for item in group.get("structures", [])
            if str(item.get("structure", "")).strip()
        )
        seeds_dir = os.path.join(workdir, "Seeds")
        os.makedirs(seeds_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=f"seed_group_{gid}_", suffix=".POSCARS", dir=seeds_dir, text=True)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.write("\n")
        ok, msg = launch_stmng_visualizer(tmp_path, STMNG_TEMPLATE_PATH)
        if not ok:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({"ok": False, "message": msg}), 400
        with STATE.lock:
            STATE.cleanup_paths.append({"path": tmp_path, "delete_after": time.time() + 10.0})
        return jsonify({"ok": True, "message": msg})

    @app.post("/api/seeds/visualize-structure")
    def api_seed_visualize_structure():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        idx = int(payload.get("index", -1))
        with STATE.lock:
            group = next((g for g in STATE.seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            items = list(group.get("structures", []))
            if idx < 0 or idx >= len(items):
                return jsonify({"ok": False, "message": "Structure not found."}), 404
            content = str(items[idx].get("structure", ""))
            workdir = STATE.workdir.strip()
        if not workdir or not os.path.isdir(workdir):
            return jsonify({"ok": False, "message": "Valid workdir is required."}), 400
        seeds_dir = os.path.join(workdir, "Seeds")
        os.makedirs(seeds_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=f"seed_struct_{gid}_{idx}_", suffix=".POSCARS", dir=seeds_dir, text=True)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content.rstrip())
            f.write("\n")
        ok, msg = launch_stmng_visualizer(tmp_path, STMNG_TEMPLATE_PATH)
        if not ok:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({"ok": False, "message": msg}), 400
        with STATE.lock:
            STATE.cleanup_paths.append({"path": tmp_path, "delete_after": time.time() + 10.0})
        return jsonify({"ok": True, "message": msg})

    @app.post("/api/antiseeds/check")
    def api_antiseeds_check():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        if not path:
            return jsonify({"ok": False, "message": "Path is required."}), 400
        try:
            info = check_structures(path)
            return jsonify({"ok": True, "info": info})
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/antiseeds/add-path")
    def api_antiseed_add_path():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        if not path:
            return jsonify({"ok": False, "message": "Path is required."}), 400
        with STATE.lock:
            try:
                group = build_seed_group(path, STATE.anti_seed_next_group_id, "manual")
            except Exception as exc:
                return jsonify({"ok": False, "message": str(exc)}), 400
            STATE.anti_seed_next_group_id += 1
            STATE.anti_seed_groups.append(group)
            STATE.anti_seeds_enabled = True
            save_config(_config_from_state())
            return jsonify({"ok": True, "message": "AntiSeed file added."})

    @app.post("/api/antiseeds/add-mp")
    def api_antiseed_add_mp():
        payload = request.get_json(force=True)
        api_key = str(payload.get("api_key", "")).strip() or STATE.anti_materials_project_api_key.strip()
        chemsys = str(payload.get("chemsys", "")).strip()
        ehull_text = str(payload.get("ehull", "")).strip()
        if not api_key:
            return jsonify({"ok": False, "message": "Materials Project API key is required."}), 400
        if not chemsys or "-" not in chemsys:
            return jsonify({"ok": False, "message": "chemsys must look like Fe-O."}), 400
        try:
            ehull = float(ehull_text)
            if ehull < 0:
                raise ValueError
        except Exception:
            return jsonify({"ok": False, "message": "Invalid e_above_hull value."}), 400
        try:
            from mp_api.client import MPRester
            from pymatgen.io.vasp import Poscar
        except Exception as exc:
            return jsonify({"ok": False, "message": f"mp_api/pymatgen missing: {exc}"}), 400

        try:
            with MPRester(api_key) as mpr:
                search_fn = mpr.materials.summary.search
                docs = None
                last_exc = None
                for arg_name in ("energy_above_hull", "e_above_hull"):
                    kwargs = {
                        "chemsys": chemsys,
                        "fields": ["material_id", "structure"],
                        "chunk_size": 50,
                        arg_name: (0, ehull),
                    }
                    try:
                        docs = search_fn(**kwargs)
                        break
                    except TypeError as exc:
                        last_exc = exc
                        continue
                    except Exception as exc:
                        msg = str(exc)
                        if "unknown to" in msg and arg_name in msg:
                            last_exc = exc
                            continue
                        raise
                if docs is None:
                    raise last_exc or RuntimeError("No compatible hull argument found.")
        except Exception as exc:
            return jsonify({"ok": False, "message": f"Materials Project request error: {exc}"}), 400
        if not docs:
            return jsonify({"ok": False, "message": "No structures found."}), 404

        structures = []
        all_elements: set[str] = set()
        systems: set[tuple[str, ...]] = set()
        for idx, doc in enumerate(docs, start=1):
            poscar = Poscar(doc.structure)
            elements = [str(x) for x in poscar.site_symbols]
            counts = [int(x) for x in poscar.natoms]
            structures.append(
                {
                    "index": idx,
                    "formula": _formula(elements, counts),
                    "Gen": None,
                    "generation": None,
                    "number": None,
                    "energy": None,
                    "structure": poscar.get_str().rstrip(),
                    "seed_generation": None,
                    "generation_user_set": False,
                }
            )
            elem_set = set(elements)
            all_elements |= elem_set
            systems.add(tuple(sorted(elem_set)))

        with STATE.lock:
            group = {
                "id": STATE.anti_seed_next_group_id,
                "path": f"Materials Project ({chemsys})",
                "source": "mp",
                "source_label": f"mp < Energy Above Hull ({ehull_text})",
                "group_generation": None,
                "stats": {
                    "count": len(structures),
                    "elements": sorted(all_elements),
                    "systems": ["-".join(x) for x in sorted(systems)],
                },
                "structures": structures,
            }
            STATE.anti_seed_next_group_id += 1
            STATE.anti_seed_groups.append(group)
            STATE.anti_seeds_enabled = True
            STATE.anti_materials_project_api_key = api_key
            STATE.anti_mp_chemsys = chemsys
            STATE.anti_mp_ehull_max = ehull_text
            save_config(_config_from_state())
            return jsonify({"ok": True, "message": f"Added {len(structures)} anti-seed structures from MP."})

    @app.post("/api/antiseeds/delete-group")
    def api_antiseed_delete_group():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        with STATE.lock:
            before = len(STATE.anti_seed_groups)
            STATE.anti_seed_groups = [g for g in STATE.anti_seed_groups if int(g.get("id", -1)) != gid]
            if len(STATE.anti_seed_groups) == before:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            save_config(_config_from_state())
            return jsonify({"ok": True})

    @app.post("/api/antiseeds/set-group-generation")
    def api_antiseed_set_group_generation():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        try:
            generation = _parse_generation_value(payload.get("generation"))
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        with STATE.lock:
            group = next((g for g in STATE.anti_seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            group["group_generation"] = generation
            for item in group.get("structures", []):
                if not bool(item.get("generation_user_set", False)):
                    item["seed_generation"] = generation
            save_config(_config_from_state())
        return jsonify({"ok": True})

    @app.post("/api/antiseeds/set-structure-generation")
    def api_antiseed_set_structure_generation():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        idx = int(payload.get("index", -1))
        try:
            generation = _parse_generation_value(payload.get("generation"))
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        with STATE.lock:
            group = next((g for g in STATE.anti_seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            items = list(group.get("structures", []))
            if idx < 0 or idx >= len(items):
                return jsonify({"ok": False, "message": "Structure not found."}), 404
            item = items[idx]
            if generation is None:
                item["generation_user_set"] = False
                item["seed_generation"] = group.get("group_generation")
            else:
                item["generation_user_set"] = True
                item["seed_generation"] = generation
            save_config(_config_from_state())
        return jsonify({"ok": True})

    @app.post("/api/antiseeds/reset-group-generations")
    def api_antiseed_reset_group_generations():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        with STATE.lock:
            group = next((g for g in STATE.anti_seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            group["group_generation"] = None
            for item in group.get("structures", []):
                item["generation_user_set"] = False
                item["seed_generation"] = None
            save_config(_config_from_state())
        return jsonify({"ok": True})

    @app.post("/api/antiseeds/delete-structure")
    def api_antiseed_delete_structure():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        idx = int(payload.get("index", -1))
        with STATE.lock:
            updated = []
            removed = False
            for g in STATE.anti_seed_groups:
                if int(g.get("id", -1)) != gid:
                    updated.append(g)
                    continue
                structures = [x for j, x in enumerate(g.get("structures", [])) if j != idx]
                if len(structures) != len(g.get("structures", [])):
                    removed = True
                if structures:
                    ng = dict(g)
                    ng["structures"] = structures
                    ng["stats"] = dict(ng.get("stats", {}))
                    ng["stats"]["count"] = len(structures)
                    updated.append(ng)
            STATE.anti_seed_groups = updated
            if not removed:
                return jsonify({"ok": False, "message": "Structure not found."}), 404
            save_config(_config_from_state())
            return jsonify({"ok": True})

    @app.post("/api/antiseeds/visualize-group")
    def api_antiseed_visualize_group():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        with STATE.lock:
            group = next((g for g in STATE.anti_seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            workdir = STATE.workdir.strip()
        if not workdir or not os.path.isdir(workdir):
            return jsonify({"ok": False, "message": "Valid workdir is required."}), 400
        text = "\n".join(
            str(item.get("structure", "")).rstrip()
            for item in group.get("structures", [])
            if str(item.get("structure", "")).strip()
        )
        anti_dir = os.path.join(workdir, "AntiSeeds")
        os.makedirs(anti_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=f"antiseed_group_{gid}_", suffix=".POSCARS", dir=anti_dir, text=True)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.write("\n")
        ok, msg = launch_stmng_visualizer(tmp_path, STMNG_TEMPLATE_PATH)
        if not ok:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({"ok": False, "message": msg}), 400
        with STATE.lock:
            STATE.cleanup_paths.append({"path": tmp_path, "delete_after": time.time() + 10.0})
        return jsonify({"ok": True, "message": msg})

    @app.post("/api/antiseeds/visualize-structure")
    def api_antiseed_visualize_structure():
        payload = request.get_json(force=True)
        gid = int(payload.get("group_id", -1))
        idx = int(payload.get("index", -1))
        with STATE.lock:
            group = next((g for g in STATE.anti_seed_groups if int(g.get("id", -1)) == gid), None)
            if group is None:
                return jsonify({"ok": False, "message": "Group not found."}), 404
            items = list(group.get("structures", []))
            if idx < 0 or idx >= len(items):
                return jsonify({"ok": False, "message": "Structure not found."}), 404
            content = str(items[idx].get("structure", ""))
            workdir = STATE.workdir.strip()
        if not workdir or not os.path.isdir(workdir):
            return jsonify({"ok": False, "message": "Valid workdir is required."}), 400
        anti_dir = os.path.join(workdir, "AntiSeeds")
        os.makedirs(anti_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=f"antiseed_struct_{gid}_{idx}_", suffix=".POSCARS", dir=anti_dir, text=True)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content.rstrip())
            f.write("\n")
        ok, msg = launch_stmng_visualizer(tmp_path, STMNG_TEMPLATE_PATH)
        if not ok:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({"ok": False, "message": msg}), 400
        with STATE.lock:
            STATE.cleanup_paths.append({"path": tmp_path, "delete_after": time.time() + 10.0})
        return jsonify({"ok": True, "message": msg})

    @app.post("/api/preview/visualize")
    def api_preview_visualize():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        ok, msg = launch_stmng_visualizer(path, STMNG_XYZ_TEMPLATE_PATH)
        if not ok:
            return jsonify({"ok": False, "message": msg}), 400
        return jsonify({"ok": True, "message": msg})

    @app.post("/api/browser/visualize")
    def api_browser_visualize():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        ok, msg = launch_stmng_visualizer(path, STMNG_TEMPLATE_PATH)
        if not ok:
            return jsonify({"ok": False, "message": msg}), 400
        return jsonify({"ok": True, "message": msg})

    @app.post("/api/preview/read-output")
    def api_preview_read_output():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        if not path or not os.path.isfile(path):
            return jsonify({"ok": False, "message": "output.xyz not found."}), 404
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return jsonify({"ok": True, "content": content})
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/browser/list")
    def api_browser_list():
        payload = request.get_json(force=True)
        root = str(payload.get("root", "")).strip()
        current = str(payload.get("current", "")).strip()
        if not root:
            return jsonify({"ok": False, "message": "Root path is required."}), 400
        root_abs = os.path.abspath(root)
        if not os.path.isdir(root_abs):
            return jsonify({"ok": False, "message": "Root path does not exist."}), 400
        current_abs = os.path.abspath(current) if current else root_abs
        if not os.path.isdir(current_abs):
            current_abs = root_abs
        try:
            names = os.listdir(current_abs)
        except Exception as exc:
            return jsonify({"ok": False, "message": f"Cannot read folder: {exc}"}), 400
        dirs = []
        files = []
        for name in names:
            full = os.path.join(current_abs, name)
            if os.path.isdir(full):
                dirs.append({"name": name, "path": full})
            elif os.path.isfile(full):
                files.append({"name": name, "path": full})
        dirs.sort(key=lambda x: x["name"].lower())
        files.sort(key=lambda x: x["name"].lower())
        parent = os.path.abspath(os.path.join(current_abs, os.pardir))
        can_go_up = current_abs != parent
        return jsonify(
            {
                "ok": True,
                "root": root_abs,
                "current": current_abs,
                "parent": parent,
                "can_go_up": can_go_up,
                "dirs": dirs,
                "files": files,
            }
        )

    @app.post("/api/browser/read")
    def api_browser_read():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        if not path or not os.path.isfile(path):
            return jsonify({"ok": False, "message": "File not found."}), 404
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return jsonify({"ok": True, "content": content})
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.get("/api/browser/file")
    def api_browser_file():
        path = request.args.get("path", "").strip()
        if not path or not os.path.isfile(path):
            return jsonify({"ok": False, "message": "File not found."}), 404
        return send_file(os.path.abspath(path))

    @app.post("/api/browser/mkdir")
    def api_browser_mkdir():
        payload = request.get_json(force=True)
        root = str(payload.get("root", "")).strip()
        current = str(payload.get("current", "")).strip()
        name = str(payload.get("name", "")).strip()
        if not root or not name:
            return jsonify({"ok": False, "message": "Root and name are required."}), 400
        base = current if (current and os.path.isdir(current)) else root
        target = os.path.join(base, name)
        try:
            os.makedirs(target, exist_ok=True)
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/browser/rename")
    def api_browser_rename():
        payload = request.get_json(force=True)
        path = str(payload.get("path", "")).strip()
        new_name = str(payload.get("new_name", "")).strip()
        if not path or not new_name:
            return jsonify({"ok": False, "message": "Path and new_name are required."}), 400
        new_path = os.path.join(os.path.dirname(path), new_name)
        try:
            os.rename(path, new_path)
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/run")
    def api_run():
        with STATE.lock:
            if STATE.running:
                return jsonify({"ok": False, "message": "Already running."}), 409
            try:
                if STATE.seeds_enabled:
                    if not STATE.workdir.strip() or not os.path.isdir(STATE.workdir.strip()):
                        raise ValueError("Set a valid workdir before running with Seeds.")
                    total = sum(len(g.get("structures", [])) for g in STATE.seed_groups)
                    if total <= 0:
                        raise ValueError("Seeds are enabled but no structures are present.")
                    ensure_seed_export(STATE.workdir.strip(), STATE.seed_groups, "Seeds", "seeds")
                if STATE.anti_seeds_enabled:
                    if not STATE.workdir.strip() or not os.path.isdir(STATE.workdir.strip()):
                        raise ValueError("Set a valid workdir before running with AntiSeeds.")
                    total_anti = sum(len(g.get("structures", [])) for g in STATE.anti_seed_groups)
                    if total_anti <= 0:
                        raise ValueError("AntiSeeds are enabled but no structures are present.")
                    ensure_seed_export(STATE.workdir.strip(), STATE.anti_seed_groups, "AntiSeeds", "anti-seeds")
                if STATE.specific_enabled:
                    if not STATE.workdir.strip() or not os.path.isdir(STATE.workdir.strip()):
                        raise ValueError("Set a valid workdir before running with Specific.")
                    ensure_specific_export(STATE.workdir.strip(), STATE.specific_files)
                expected_preview = _build_input_preview()
                if not STATE.preview_dirty:
                    STATE.preview_text = expected_preview
                logic.write_input_file(STATE.workdir, STATE.preview_text or expected_preview)
                proc = logic.start_uspex_process(STATE.exe_path, STATE.workdir)
                STATE.proc = proc
                STATE.monitor = logic.UspexMonitor()
                STATE.status = STATE.monitor.to_dict()
                STATE.history = []
                STATE.log_lines = []
                STATE.error = ""
                STATE.running = True
                thread = threading.Thread(target=_reader_loop, args=(proc,), daemon=True)
                thread.start()
                save_config(_config_from_state())
            except Exception as exc:
                STATE.error = str(exc)
                return jsonify({"ok": False, "message": str(exc)}), 400
            return jsonify({"ok": True})

    @app.post("/api/stop")
    def api_stop():
        with STATE.lock:
            if STATE.proc is None:
                return jsonify({"ok": True, "message": "Not running."})
            logic.stop_uspex_process(STATE.proc)
            return jsonify({"ok": True, "message": "Stop signal sent."})

    @app.get("/api/log")
    def api_log():
        since = int(request.args.get("since", "0"))
        with STATE.lock:
            current = STATE.log_version
            lines = STATE.log_lines[-LOG_MAX_LINES:]
            if since >= current:
                return jsonify({"version": current, "lines": []})
            return jsonify({"version": current, "lines": lines})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=True)
