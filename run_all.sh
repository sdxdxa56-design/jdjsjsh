#!/bin/bash
set -e
echo "[*] Building and running local fuzzer with ASan/UBSan..."
clang -g -O1 -fsanitize=fuzzer,address,undefined -o fuzz_demo targets/demo.c harnesses/h.c
./fuzz_demo seeds/ -max_total_time=30
