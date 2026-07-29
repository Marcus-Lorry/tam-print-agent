# Shazada print agent — install (per counter PC, one time)

Prints invoices straight to the Xprinter T80Q (80mm thermal) — no browser print
dialog. If the agent isn't running, the admin site automatically falls back to
the old browser-print flow, so rollout is safe and gradual.

No certificate, no admin rights, no Chrome restart needed.

## Steps

1. Copy `shazada-print-agent.exe` onto the PC, e.g. `C:\ShazadaPrintAgent\`.
2. Double-click it once. It creates `config.json` next to the exe and starts
   listening on `http://127.0.0.1:17777`.
3. Open `config.json` and set the printer's USB IDs:
   - Windows **Device Manager -> Xprinter T80Q -> Details tab -> "Hardware Ids"**
   - You'll see something like `USB\VID_0483&PID_5743...`
   - Put `"0x0483"` into `printer.usb.vendor_id` and `"0x5743"` into
     `printer.usb.product_id` (use YOUR printer's values).
   - `allowed_origin` is already set to `https://shazadalogistics.com` — leave it.
   - Printer on the LAN instead of USB? Set `"mode": "network"` and fill in
     `printer.network.host` (its IP) and `port` (usually 9100).
4. Save `config.json`, then make the agent start on login: press `Win+R`, type
   `shell:startup`, press Enter, and drop a **shortcut** to the exe into that folder.
5. Restart the exe (close the window, run it again) so it picks up your config.

## Verify

- Visit `http://127.0.0.1:17777/health` in the browser -> small JSON status page.
- Or set `"mode": "dummy"` in `config.json` first, restart the exe, and print
  from the admin site: it "prints" (returns success) with no hardware attached,
  proving the whole browser -> agent chain works. Then switch `mode` back to `usb`.

## Troubleshooting

- If you still get the browser print dialog, the agent isn't reachable: either
  it isn't running, or `allowed_origin` doesn't EXACTLY match the site URL
  (`https://shazadalogistics.com`, no trailing slash).
- Wrong VID/PID or printer off -> the agent returns an error and the site falls
  back to browser print. Fix the IDs / power and restart the exe.
