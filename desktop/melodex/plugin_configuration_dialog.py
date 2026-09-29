from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)


def configure_plugin(
    parent: QWidget,
    manager,
    plugin_id: str,
    *,
    setup: bool = False,
) -> dict[str, Any] | None:
    """Show the shared provider/extension configuration dialog.

    Returns the resulting status after a successful save, or None when the
    dialog is cancelled / the plugin has no declared configuration.
    """
    try:
        info = dict(manager.plugin_configuration(str(plugin_id)) or {})
    except Exception as exc:
        QMessageBox.warning(parent, "Plugin configuration", str(exc))
        return None

    fields = list(info.get("fields") or [])
    if not fields:
        if not setup:
            QMessageBox.information(
                parent,
                "Plugin configuration",
                f"{info.get('name') or plugin_id} does not require any setup.",
            )
        return dict(info.get("status") or {"ready": True, "declared": False})

    dialog = QDialog(parent)
    title_name = str(info.get("name") or plugin_id)
    dialog.setWindowTitle(
        f"Set up {title_name}" if setup else f"Configure {title_name}"
    )
    layout = QVBoxLayout(dialog)

    intro = QLabel(
        (
            "This plugin needs a little setup before it is ready. "
            if setup
            else ""
        )
        + "Melodex sends only the values declared by this plugin. "
        "Secret fields are stored in the system credential store when available."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    form = QFormLayout()
    layout.addLayout(form)
    current = dict(info.get("values") or {})
    status = dict(info.get("status") or {})
    configured = dict(status.get("configured") or {})
    widgets: dict[str, tuple[dict[str, Any], QWidget]] = {}

    for field in fields:
        key = str(field.get("key") or "")
        label = str(field.get("label") or key)
        if field.get("required"):
            label += " *"
        field_type = str(field.get("type") or "string")
        if field_type == "boolean":
            widget = QCheckBox()
            widget.setChecked(bool(current.get(key, False)))
        else:
            line = QLineEdit()
            if field_type == "secret":
                line.setEchoMode(QLineEdit.EchoMode.Password)
                line.setPlaceholderText(
                    "Stored — leave blank to keep"
                    if configured.get(key)
                    else "Enter secret"
                )
            else:
                line.setText(str(current.get(key) or ""))
            help_text = str(field.get("help") or "")
            if help_text:
                line.setToolTip(help_text)
            widget = line
        widgets[key] = (field, widget)
        form.addRow(label, widget)

    if any(str(field.get("type")) == "secret" for field in fields):
        storage = str(status.get("secret_storage") or "")
        note = QLabel(f"Secret storage: {storage or 'session-only'}")
        note.setWordWrap(True)
        layout.addWidget(note)

    validation = QLabel("")
    validation.setWordWrap(True)
    validation.setStyleSheet("color:#e8a34a")
    layout.addWidget(validation)

    buttons = QDialogButtonBox(
        QDialogButtonBox.Save | QDialogButtonBox.Cancel
    )
    layout.addWidget(buttons)
    result_status: dict[str, Any] = {}

    def save() -> None:
        changes: dict[str, Any] = {}
        for key, (field, widget) in widgets.items():
            field_type = str(field.get("type") or "string")
            if field_type == "boolean":
                assert isinstance(widget, QCheckBox)
                changes[key] = widget.isChecked()
            else:
                assert isinstance(widget, QLineEdit)
                text = widget.text()
                changes[key] = (
                    None if field_type == "secret" and not text else text
                )
        try:
            updated = dict(
                manager.set_plugin_configuration(str(plugin_id), changes) or {}
            )
        except Exception as exc:
            QMessageBox.critical(
                dialog, "Could not save configuration", str(exc)
            )
            return

        if not updated.get("ready", True):
            missing = [str(x) for x in updated.get("missing_required") or []]
            labels = {
                str(field.get("key") or ""): str(
                    field.get("label") or field.get("key") or ""
                )
                for field in fields
            }
            names = [labels.get(key, key) for key in missing]
            validation.setText(
                "Required before this plugin is ready: " + ", ".join(names)
            )
            return

        result_status.clear()
        result_status.update(updated)
        dialog.accept()

    save_button = buttons.button(QDialogButtonBox.Save)
    save_button.clicked.connect(save)
    cancel_button = buttons.button(QDialogButtonBox.Cancel)
    cancel_button.clicked.connect(dialog.reject)

    if dialog.exec() != QDialog.Accepted:
        return None
    return result_status
