from __future__ import annotations

import ipaddress
import json
import socket
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
)


def bridge_lan_address() -> str:
    # A UDP connect only selects the route; it sends no packet to this reserved address.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            address = str(probe.getsockname()[0])
            parsed = ipaddress.ip_address(address)
            if parsed.is_private and not parsed.is_loopback:
                return address
    except OSError:
        pass

    candidates: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = str(info[4][0])
            if address and not address.startswith("127.") and address != "0.0.0.0":
                if address not in candidates:
                    candidates.append(address)
    except OSError:
        pass
    for address in candidates:
        try:
            parsed = ipaddress.ip_address(address)
            if parsed.is_private and not parsed.is_loopback:
                return address
        except ValueError:
            continue
    return candidates[0] if candidates else ""


def _render_pairing_qr(label: QLabel, payload: str) -> None:
    import segno

    matrix = segno.make_qr(payload).matrix
    border = 4
    scale = max(4, min(8, 384 // (len(matrix) + border * 2)))
    side = (len(matrix) + border * 2) * scale
    image = QImage(side, side, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(Qt.GlobalColor.black)
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                painter.drawRect(
                    (x + border) * scale,
                    (y + border) * scale,
                    scale,
                    scale,
                )
    painter.end()
    label.setPixmap(QPixmap.fromImage(image))


def _show_pairing_dialog(
    parent: QMainWindow,
    bridge: Any,
    restrict_bridge: Callable[[], None],
) -> None:
    address = bridge_lan_address()
    if not address:
        QMessageBox.warning(
            parent,
            "Provider Bridge",
            "Melodex could not find this computer's local network address. "
            "Check that it is connected to the same Wi-Fi as the phone.",
        )
        return

    bridge_url = f"http://{address}:{bridge.port}"
    dialog = QDialog(parent)
    dialog.setWindowTitle("Connect Android to Melodex")
    dialog_layout = QVBoxLayout(dialog)
    dialog_layout.addWidget(
        QLabel("Scan this code with Melodex on your Android phone.")
    )

    qr_label = QLabel()
    qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    qr_label.setAccessibleName("Melodex Bridge pairing QR code")
    dialog_layout.addWidget(qr_label)

    code_status = QLabel()
    code_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dialog_layout.addWidget(code_status)

    manual_details = QLabel()
    manual_details.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )
    manual_details.hide()
    manual_button = QPushButton("Show advanced manual setup")

    def toggle_manual_details() -> None:
        if manual_details.isVisible():
            manual_details.hide()
            manual_button.setText("Show advanced manual setup")
        else:
            manual_details.setText(
                f"Bridge URL: {bridge_url}\n"
                f"Bridge token: {bridge.token}\n"
                "Treat the token like a password. It changes when the Bridge restarts."
            )
            manual_details.show()
            manual_button.setText("Hide advanced manual setup")

    manual_button.clicked.connect(toggle_manual_details)
    dialog_layout.addWidget(manual_button)
    dialog_layout.addWidget(manual_details)

    refresh_button = QPushButton("Refresh QR code")
    dialog_layout.addWidget(refresh_button)

    dialog_layout.addWidget(QLabel("Paired phones"))
    paired_list = QListWidget()
    paired_list.setMaximumHeight(120)
    dialog_layout.addWidget(paired_list)

    device_status = QLabel()
    dialog_layout.addWidget(device_status)

    def refresh_devices() -> None:
        paired_list.clear()
        for device in bridge.paired_devices():
            item = QListWidgetItem(str(device.get("name") or "Android device"))
            item.setData(Qt.ItemDataRole.UserRole, str(device.get("id") or ""))
            paired_list.addItem(item)
        device_status.setText(
            "No phones paired yet."
            if paired_list.count() == 0
            else "Each phone has its own access token. Forget a phone to revoke its access."
        )

    def refresh_qr() -> None:
        code = bridge.new_pairing_code()
        payload = json.dumps(
            {
                "type": "melodex-bridge-pairing",
                "version": 1,
                "url": bridge_url,
                "code": code,
                "name": socket.gethostname() or "Melodex computer",
            },
            separators=(",", ":"),
        )
        _render_pairing_qr(qr_label, payload)
        code_status.setText(
            "Code expires in two minutes. Phone and computer must share this trusted LAN.\n"
            f"Bridge address: {bridge_url}"
        )

    def forget_selected() -> None:
        item = paired_list.currentItem()
        if item is None:
            device_status.setText("Select a paired phone to forget it.")
            return
        device_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if bridge.revoke_paired_device(device_id):
            device_status.setText(f"Access revoked for {item.text()}.")
        refresh_devices()

    def forget_all() -> None:
        if not bridge.paired_devices():
            return
        answer = QMessageBox.question(
            dialog,
            "Forget all paired phones?",
            "Every paired phone will need to scan a new QR code.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            count = bridge.revoke_all_paired_devices()
            device_status.setText(f"Revoked access for {count} paired phone(s).")
            refresh_devices()

    refresh_button.clicked.connect(refresh_qr)
    refresh_devices()
    refresh_qr()

    device_buttons = QHBoxLayout()
    forget_button = QPushButton("Forget selected")
    forget_button.clicked.connect(forget_selected)
    forget_all_button = QPushButton("Forget all")
    forget_all_button.clicked.connect(forget_all)
    device_buttons.addWidget(forget_button)
    device_buttons.addWidget(forget_all_button)
    dialog_layout.addLayout(device_buttons)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    dialog_layout.addWidget(buttons)

    if bridge.host != "127.0.0.1":
        restrict_button = QPushButton("Restrict to this computer")

        def restrict_to_computer() -> None:
            dialog.accept()
            restrict_bridge()

        restrict_button.clicked.connect(restrict_to_computer)
        device_buttons.addWidget(restrict_button)

    dialog.resize(430, 650)
    dialog.exec()


def show_provider_bridge_dialog(
    parent: QMainWindow,
    *,
    get_bridge: Callable[[], Any],
    start_bridge: Callable[[], None],
    bridge_start_pending: Callable[[], bool],
    restart_bridge: Callable[[str], None],
) -> None:
    bridge = get_bridge()
    if not bridge:
        start_bridge()
        if bridge_start_pending():
            parent.statusBar().showMessage(
                "AI control bridge is starting in the background…",
                3000,
            )
        return

    if bridge.host == "127.0.0.1":
        choice = QMessageBox.question(
            parent,
            "Provider Bridge",
            "Allow phones and computers on your local network to use the Provider Bridge? "
            "Choose No to keep it available only on this computer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            restart_bridge("0.0.0.0")
        except Exception as exc:
            QMessageBox.warning(
                parent,
                "Provider Bridge",
                f"Could not enable LAN access: {exc}",
            )
            return
        bridge = get_bridge()

    if bridge is None or bridge.host == "127.0.0.1":
        return

    def restrict_to_computer() -> None:
        try:
            restart_bridge("127.0.0.1")
            parent.statusBar().showMessage(
                "Provider bridge restricted to this computer",
                4000,
            )
        except Exception as exc:
            parent.statusBar().showMessage(str(exc), 7000)

    _show_pairing_dialog(parent, bridge, restrict_to_computer)
