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
        for row in data["items"]["rows"]:
            p.textln(" | ".join(str(cell) for cell in row))

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
            p.textln(note["text"])

        self._rule(p)
        p.set(align="center", bold=False)
        for line in data["footer"]:
            p.textln(line)
