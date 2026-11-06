#!/bin/bash
echo "[*] Building and running local fuzzer..."
clang -g -O1 -fsanitize=fuzzer,address,undefined -o fuzz_demo targets/demo.c harnesses/h.c
./fuzz_demo
