#include <stdint.h>
#include <stddef.h>
int parse(const uint8_t*, size_t);
int LLVMFuzzerTestOneInput(const uint8_t *d, size_t s){ parse(d,s); return 0; }
