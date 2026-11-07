// Copy to secrets.h (git ignores it) and paste the bin token. It sits next to
// local_settings.h, which holds the Wi-Fi password. The detection server
// refuses scans that don't send this token in the X-Bin-Token header.
#pragma once

#define BIN_TOKEN "paste the token here"
