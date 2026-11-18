#include <stdint.h>
#include <stddef.h>

int parse(const uint8_t *d, size_t s);

int LLVMFuzzerTestOneInput(const uint8_t *d, size_t s) {
    parse(d, s);
    return 0;
}
