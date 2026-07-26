import os
import re
import subprocess
from collections import defaultdict

import numpy as np
from chemparse import parse_formula


DEFAULT_USPEX_EXE = ""

GEN_RE = re.compile(r"==\s*Generation\s+(\d+)\s+started\s*==")
PRELIM_SIZE_RE = re.compile(r"preliminary generation size:\s*(\d+)")
ADDED_STRUCTURES_RE = re.compile(r"Added\s+(\d+)\s+structures\s+to\s+generation\s+(\d+)", re.IGNORECASE)
FREED_RE = re.compile(r"Freed cores \[.*?\] from job \(system\s+(\d+),\s*step\s+(\d+)\)")
STAGE_RELAX_RE = re.compile(r"\*\s*2\.\s*RELAXATION\s*\*")
STAGE_PROP_RE = re.compile(r"\*\s*3\.\s*PROPERTIES CALCULATION\s*\*")
RELAX_DONE_RE = re.compile(r"Parallel relaxation done for all structures\.", re.IGNORECASE)
_COEF_RE = re.compile(r"^\s*(\d+)\s*([A-Za-z(].*)\s*$")


def parse_elements(text: str) -> list[str]:
    parts = [p.strip() for p in text.replace(",", " ").split()]
    return [p for p in parts if p]


def parse_int_list(text: str) -> list[int]:
    parts = [p.strip() for p in text.replace(",", " ").split()]
    out = []
    for p in parts:
        if p:
            out.append(int(p))
    return out


def parse_with_coef(token: str) -> dict[str, int]:
    """
    Understands:
      - Na2O
      - 3Pb(NO3)2
      - 2Na2O  -> multiplies by 2
      - 2Na    -> {'Na': 2}
    """
    m = _COEF_RE.match(token)
    if m:
        coef = int(m.group(1))
        formula = m.group(2)
    else:
        coef = 1
        formula = token.strip()

    parsed = parse_formula(formula)
    return {el: cnt * coef for el, cnt in parsed.items()}


def count_elements(formula_string: str) -> tuple[str, str]:
    """
    Accepts a space/comma-separated string of formulas or elements and returns:
    (elements_str, matrix_str)
    """
    total_counts: dict[str, int] = defaultdict(int)
    formulas = formula_string.replace(",", " ").split()
    for formula in formulas:
        parsed = parse_with_coef(formula)
        for element, count in parsed.items():
            total_counts[element] += count

    elements_count = dict(total_counts)
    elements = " ".join(elements_count.keys())
    values = list(elements_count.values())
    if not values:
        return "", ""
    matrix = "\n".join(
        " ".join(f"{x:g}" for x in row)
        for row in np.diag(values)
    )
    return elements, matrix


def gen_fixed_composition(elements: list[str], counts: list[int]) -> str:
    elems = " ".join(elements)
    nums = " ".join(str(x) for x in counts)
    return (
        "% atomType\n"
        f"{elems}\n"
        "% EndAtomType\n\n"
        "% numSpecies\n"
        f"{nums}\n"
        "% EndNumSpecies\n"
    )


def gen_single_block(elements: list[str], ratios: list[int], min_at: int, max_at: int) -> str:
    elems = " ".join(elements)
    nums = " ".join(str(x) for x in ratios)
    return (
        "% atomType\n"
        f"{elems}\n"
        "% EndAtomType\n\n"
        "% numSpecies\n"
        f"{nums}\n"
        "% EndNumSpecies\n\n"
        f"{min_at}    : minAt\n"
        f"{max_at}    : maxAt\n"
    )


def gen_variable_composition(elements: str, matrix: str, min_at: int, max_at: int) -> str:
    elems = elements
    return (
        "% atomType\n"
        f"{elems}\n"
        "% EndAtomType\n\n"
        "% numSpecies\n"
        f"{matrix}\n"
        "% EndNumSpecies\n\n"
        f"{min_at}    : minAt\n"
        f"{max_at}    : maxAt\n"
    )


def build_input_fixed(elements: list[str], counts: list[int]) -> str:
    if not elements:
        raise ValueError("Enter at least one element.")
    if len(counts) != len(elements):
        raise ValueError("Counts must match number of elements.")
    return gen_fixed_composition(elements, counts)


def build_input_single(elements: list[str], ratios: list[int], min_at: int, max_at: int) -> str:
    if not elements:
        raise ValueError("Enter at least one element.")
    if len(ratios) != len(elements):
        raise ValueError("Ratios must match number of elements.")
    if min_at <= 0:
        raise ValueError("minAt must be > 0.")
    if max_at < min_at:
        raise ValueError("maxAt must be >= minAt.")
    return gen_single_block(elements, ratios, min_at, max_at)


def build_input_variable(formula_string: str, min_at: int, max_at: int) -> str:
    elements, matrix = count_elements(formula_string)
    if not elements:
        raise ValueError("Enter at least one element or formula.")
    if min_at <= 0:
        raise ValueError("minAt must be > 0.")
    if max_at < min_at:
        raise ValueError("maxAt must be >= minAt.")
    return gen_variable_composition(elements, matrix, min_at, max_at)


def write_input_file(workdir: str, text: str) -> str:
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, "INPUT.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def start_uspex_process(exe_path: str, workdir: str) -> subprocess.Popen:
    if not exe_path or not os.path.isfile(exe_path):
        raise FileNotFoundError("Invalid uspex.exe path.")
    if not workdir:
        raise ValueError("Workdir is required.")
    os.makedirs(workdir, exist_ok=True)
    creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    return subprocess.Popen(
        [exe_path],
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags,
    )


def stop_uspex_process(proc: subprocess.Popen) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=2)
        return
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "uspex.exe"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        pass


class UspexMonitor:
    def __init__(self):
        self.current_gen = None
        self.gen_size = None
        self.total_relax_steps = None
        self.relax_seen = set()
        self.stage = "idle"

    def reset_for_generation(self, gen: int) -> dict:
        self.current_gen = gen
        self.gen_size = None
        self.total_relax_steps = None
        self.relax_seen.clear()
        self.stage = "generation"
        return self.to_dict()

    def to_dict(self) -> dict:
        return {
            "generation": self.current_gen,
            "gen_size": self.gen_size,
            "stage": self.stage,
            "done_steps": len(self.relax_seen),
            "total_steps": self.total_relax_steps,
        }

    def feed_line(self, line: str) -> dict | None:
        m = GEN_RE.search(line)
        if m:
            return self.reset_for_generation(int(m.group(1)))

        m = ADDED_STRUCTURES_RE.search(line)
        if m:
            gen_size = int(m.group(1))
            gen_num = int(m.group(2))
            if self.current_gen != gen_num:
                self.reset_for_generation(gen_num)
            self.gen_size = gen_size
            self.total_relax_steps = self.gen_size * 3
            if self.stage == "idle":
                self.stage = "generation"
            return self.to_dict()

        m = PRELIM_SIZE_RE.search(line)
        if m:
            self.gen_size = int(m.group(1))
            self.total_relax_steps = self.gen_size * 3
            return self.to_dict()

        if STAGE_RELAX_RE.search(line):
            self.stage = "relaxation"
            return self.to_dict()

        if RELAX_DONE_RE.search(line):
            self.stage = "relaxation_done"
            return self.to_dict()

        if STAGE_PROP_RE.search(line):
            self.stage = "properties"
            return self.to_dict()

        m = FREED_RE.search(line)
        if m:
            system = int(m.group(1))
            step = int(m.group(2))
            key = (system, step)
            if key not in self.relax_seen:
                self.relax_seen.add(key)
                if self.stage not in ("properties",):
                    self.stage = "relaxation"
                return self.to_dict()
        return None
