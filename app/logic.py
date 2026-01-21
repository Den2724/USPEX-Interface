import os
import re
import subprocess


DEFAULT_USPEX_EXE = r"C:\Users\andre\Downloads\USPEX_25_windows\uspex.exe"

GEN_RE = re.compile(r"==\s*Generation\s+(\d+)\s+started\s*==")
PRELIM_SIZE_RE = re.compile(r"preliminary generation size:\s*(\d+)")
FREED_RE = re.compile(r"Freed cores \[.*?\] from job \(system\s+(\d+),\s*step\s+(\d+)\)")
STAGE_RELAX_RE = re.compile(r"\*\s*2\.\s*RELAXATION\s*\*")
STAGE_PROP_RE = re.compile(r"\*\s*3\.\s*PROPERTIES CALCULATION\s*\*")
RELAX_DONE_RE = re.compile(r"Parallel relaxation done for all structures\.", re.IGNORECASE)


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


def gen_variable_composition(elements: list[str], min_at: int, max_at: int) -> str:
    elems = " ".join(elements)
    n = len(elements)
    lines = []
    for i in range(n):
        row = ["0"] * n
        row[i] = "1"
        lines.append(" ".join(row))
    matrix = "\n".join(lines)
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


def build_input_variable(elements: list[str], min_at: int, max_at: int) -> str:
    if not elements:
        raise ValueError("Enter at least one element.")
    if min_at <= 0:
        raise ValueError("minAt must be > 0.")
    if max_at < min_at:
        raise ValueError("maxAt must be >= minAt.")
    return gen_variable_composition(elements, min_at, max_at)


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
    return subprocess.Popen(
        [exe_path],
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
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
