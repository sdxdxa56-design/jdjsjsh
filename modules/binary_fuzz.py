import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def run_libfuzzer_on_target(
    source_file: str,
    harness_code: Optional[str] = None,
    timeout_sec: int = 60,
) -> Dict[str, Any]:
    """Compiles C/C++ target with libFuzzer + ASan/UBSan and runs a bounded fuzzing session."""
    crashes_dir = Path("crashes")
    corpus_dir = Path("corpus")
    crashes_dir.mkdir(exist_ok=True)
    corpus_dir.mkdir(exist_ok=True)

    harness_path = Path("harnesses/generated_harness.c")
    if harness_code and "LLVMFuzzerTestOneInput" in harness_code:
        harness_path.parent.mkdir(parents=True, exist_ok=True)
        harness_path.write_text(harness_code, encoding="utf-8")
    else:
        harness_path = Path("harnesses/h.c")

    binary_path = Path("./fuzz_target")
    compile_cmd = [
        "clang",
        "-g",
        "-O1",
        "-fsanitize=fuzzer,address,undefined",
        "-o",
        str(binary_path),
        source_file,
        str(harness_path),
    ]

    comp = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
    if comp.returncode != 0:
        return {
            "compiled": False,
            "crashed": False,
            "compile_error": comp.stderr[-1500:],
            "asan_log": "",
            "crash_file": "",
        }

    seeds_arg = ["seeds/"] if Path("seeds").exists() else []
    fuzz_cmd = [
        str(binary_path),
        str(corpus_dir),
        *seeds_arg,
        f"-max_total_time={timeout_sec}",
        f"-artifact_prefix={crashes_dir}/",
    ]
    run = subprocess.run(fuzz_cmd, capture_output=True, text=True, timeout=timeout_sec + 30)
    combined = (run.stdout or "") + "\n" + (run.stderr or "")
    crash_files = sorted(crashes_dir.glob("crash-*")) + sorted(crashes_dir.glob("oom-*")) + sorted(crashes_dir.glob("timeout-*"))

    crashed = len(crash_files) > 0 or "ERROR: AddressSanitizer" in combined or "ERROR: UndefinedBehaviorSanitizer" in combined
    return {
        "compiled": True,
        "crashed": crashed,
        "compile_error": "",
        "asan_log": combined[-3000:],
        "crash_file": str(crash_files[0]) if crash_files else "",
    }
