"""Render a receipt JSON payload (from Invoice::toReceiptArray()) onto an ESC/POS printer.

Deliberately dumb: every string here already comes pre-formatted from Laravel
(see app/Models/Invoice.php::toReceiptArray()), so this module only concerns
itself with turning that data into ESC/POS calls — no money/locale logic.
"""
from __future__ import annotations

from escpos.printer import Dummy, Network, Usb


class ReceiptPrinter:
    def __init__(self, config: dict):
        self._config = config
        self.chars_per_line = config.get("chars_per_line", 42)

    def _open(self):
        printer_cfg = self._config.get("printer", {})
        mode = printer_cfg.get("mode", "usb")
        if mode == "usb":
            usb_cfg = printer_cfg["usb"]
            return Usb(int(usb_cfg["vendor_id"], 16), int(usb_cfg["product_id"], 16), profile="default")
        if mode == "network":
            net_cfg = printer_cfg["network"]
            return Network(net_cfg["host"], net_cfg.get("port", 9100), profile="default")
        if mode == "dummy":
            return Dummy()
        raise ValueError(f"Unknown printer mode: {mode!r}")

    def print_receipt(self, data: dict) -> bytes | None:
        p = self._open()
        try:
            self._render(p, data)
            p.cut()
            if isinstance(p, Dummy):
                return p.output
        finally:
            if not isinstance(p, Dummy):
                p.close()
        return None

    def _line(self, left: str = "", right: str = "") -> str:
        if not right:
            return left
        pad = max(1, self.chars_per_line - len(left) - len(right))
        return left + " " * pad + right

    def _rule(self, p):
        p.textln("-" * self.chars_per_line)

    def _wrap(self, text: str):
        """Word-wrap a line to the printer width so it never overflows into an
        ugly mid-word wrap done by the printer's own firmware."""
        text = str(text)
        if len(text) <= self.chars_per_line:
            return [text]
        out, cur = [], ""
        for word in text.split(" "):
            if not cur:
                cur = word
            elif len(cur) + 1 + len(word) <= self.chars_per_line:
                cur += " " + word
            else:
                out.append(cur)
                cur = word
            # a single word longer than the line: hard-split it
            while len(cur) > self.chars_per_line:
                out.append(cur[: self.chars_per_line])
                cur = cur[self.chars_per_line:]
        if cur:
            out.append(cur)
        return out

    def _item(self, p, index, title, meta="", qty="", price=""):
        """One invoice line item across (up to) two rows, sized to the paper:
        line 1 = "N. Title .......... Price" (title truncated so it never wraps),
        line 2 = "   Qty · #Barcode"  (the details, indented). Because the items
        table has 5-6 columns it can't fit legibly on one 42/48-char line."""
        head = (f"{index}. " if str(index).strip() else "") + str(title).strip()
        price = str(price).strip()
        room = self.chars_per_line - len(price) - 1
        if room > 3 and len(head) > room:
            head = head[: room - 2].rstrip() + ".."
        p.textln(self._line(head, price))
        details = " · ".join(x for x in (str(qty).strip(), (f"#{meta}".strip() if str(meta).strip() else "")) if x)
        if details:
            for ln in self._wrap("   " + details):
                p.textln(ln)

    def _render(self, p, data: dict) -> None:
        p.set(align="center", bold=True)
        p.textln("SHAZADA")
        p.set(align="left", bold=False)
        p.textln(self._line(data["invoice_number"], data["created_at"]))
        self._rule(p)

        customer = data.get("customer")
        if customer:
            p.set(bold=True)
            p.textln(customer["section_title"])
            p.set(bold=False)
            p.textln(f"{customer['code_label']}: {customer['code']}")
            if customer["delivery"]:
                p.textln(f"{customer['delivery']['label']}: {customer['delivery']['value']}")
            p.textln(f"{customer['username_label']}: {customer['username']}")
            p.textln(f"{customer['name_label']}: {customer['name']}")
            if customer["phone"]:
                p.textln(f"{customer['phone']['label']}: {customer['phone']['value']}")

        shipping = data.get("shipping")
        if shipping:
            p.set(bold=True)
            p.textln(shipping["section_title"])
            p.set(bold=False)
            if shipping["transport"]:
                t = shipping["transport"]
                p.textln(f"{t['label']}: {t['code']}")
                p.textln(f"{t['type_label']}: {t['type']}")
            if shipping["warehouse"]:
                w = shipping["warehouse"]
                p.textln(f"{w['label']}: {w['name']}")

        self._rule(p)

        p.set(bold=True)
        p.textln(data["items_section_title"])
        p.set(bold=False)
        is_custom = data.get("is_custom", False)
        usd = data.get("usd", False)
        for row in data["items"]["rows"]:
            row = [str(c) for c in row]
            if is_custom:
                # custom row: [idx, title, "qty unit", price...] where price is
                # one cell ($usd) or two cells (tmt, cny).
                index, title, qty = row[0], row[1], row[2]
                prices = row[3:]
                price = prices[0] if usd else (f"{prices[0]}TMT/{prices[1]}¥" if len(prices) >= 2 else "".join(prices))
                meta = ""
            else:
                # non-custom row: [idx, barcode, type, unit, qty, price].
                index, barcode, typ, unit, qty_raw, price = (row + [""] * 6)[:6]
                title, meta = typ, barcode
                qty = f"{qty_raw} {unit}".strip()
            self._item(p, index, title, meta, qty, price)

        self._rule(p)

        totals = data["totals"]
        p.set(bold=True)
        p.textln(totals["section_title"])
        p.set(bold=False)
        if totals["subtotal"]:
            p.textln(self._line(totals["subtotal"]["label"] + ":", totals["subtotal"]["amount"]))
        if totals["discount"]:
            p.textln(self._line(totals["discount"]["label"] + ":", totals["discount"]["amount"]))
        p.set(bold=True, double_height=True)
        p.textln(self._line(totals["total"]["label"] + ":", totals["total"]["amount"]))
        if totals["delivery"]:
            p.textln(self._line(totals["delivery"]["label"] + ":", totals["delivery"]["amount"]))
        p.set(bold=False, double_height=False)

        note = data.get("note")
        if note:
            self._rule(p)
            p.set(bold=True)
            p.textln(note["label"])
            p.set(bold=False)
            for ln in self._wrap(note["text"]):
                p.textln(ln)

        self._rule(p)
        p.set(align="center", bold=False)
        for line in data["footer"]:
            for ln in self._wrap(line):
                p.textln(ln)
