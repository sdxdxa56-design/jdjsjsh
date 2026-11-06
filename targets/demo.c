#include <stdint.h>
#include <string.h>
int parse(const uint8_t *d, size_t s) { if (s < 2) return -1; uint8_t e[32]; uint8_t len = d[1]; if (len > s-2) return -1; memcpy(e, d+2, len); return 0; }
