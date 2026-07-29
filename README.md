# Shazada print agent

A small local Windows service that receives invoice receipt data from the
admin site's browser and prints it directly to the Xprinter T80Q via ESC/POS
— no browser print dialog, no OS print-driver rasterization, so the thermal
output stays crisp.

The admin site falls back to the old browser-print-dialog flow automatically
if this agent isn't running, so it's safe to roll out gradually.

## Staff setup (one time, on the counter PC)

1. Copy `shazada-print-agent.exe` to the counter PC (e.g. `C:\ShazadaPrintAgent\`).
2. Double-click it once. This creates `config.json` (from `config.example.json`).
3. Edit `config.json` next to the exe:
   - `allowed_origin`: the exact admin site URL (e.g. `https://admin.shazada.com`).
     Must match exactly — it's the only origin the agent will accept.
   - `printer.mode`: `"usb"` (current setup) or `"network"` if the printer is
     later moved to the LAN.
   - `printer.usb.vendor_id` / `product_id`: read from Windows Device Manager
     → the Xprinter T80Q entry → Details tab → "Hardware Ids" (format like
     `USB\VID_0483&PID_5743...` — use the `0x0483` / `0x5743` parts).
4. Make it start automatically: press `Win+R`, type `shell:startup`, press
   Enter, then drop a shortcut to `shazada-print-agent.exe` into that folder.

No certificate to install: the agent serves plain HTTP on `127.0.0.1`, which
browsers treat as a secure origin, so the HTTPS admin page can call it directly.
Check it's up by visiting `http://127.0.0.1:17777/health`.

## Building the exe from source

```
cd print-agent
pip install -r requirements.txt pyinstaller
pyinstaller build.spec
```

Output is `dist/shazada-print-agent.exe`.

## Testing without the physical printer

Set `"mode": "dummy"` in `config.json` and restart the agent. `/print` will
still respond `200 {"success": true}` but nothing is sent to a real device —
useful for testing the Laravel → browser → agent chain end to end before
hardware is available.
