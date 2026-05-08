from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from .converter import ExportSettings, load_rgba_frame, render_preview_frame, save_gif
from .sequence import SequenceGroup, choose_primary_sequence, detect_sequences, group_selected_files


@dataclass(slots=True)
class LoadedSequence:
    group: SequenceGroup
    source_folder: Path | None = None


class PreviewLabel(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self._aspect_ratio = 16 / 9
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_aspect_ratio(self, width: int, height: int) -> None:
        self._aspect_ratio = max(width, 1) / max(height, 1)
        self.updateGeometry()

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return max(220, round(width / max(self._aspect_ratio, 1e-6)))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sequence to GIF")
        self.resize(1180, 760)

        self.loaded_sequence: LoadedSequence | None = None
        self.current_frame_rgba = None
        self.current_matte_color = (18, 18, 22)
        self.source_aspect_ratio = 1.0
        self.source_width = 0
        self.source_height = 0
        self.detected_group_count = 0

        self._build_ui()
        self._apply_dark_theme()
        self._update_controls_enabled(False)
        self._update_matte_button()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QLabel("Sequence to GIF")
        header.setObjectName("headerTitle")
        subheader = QLabel(
            "Convert JPG, PNG, or EXR sequences into animated GIFs with resize, timing, alpha, and matte controls."
        )
        subheader.setWordWrap(True)

        layout.addWidget(header)
        layout.addWidget(subheader)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        left_column = QVBoxLayout()
        left_column.setSpacing(16)
        left_column.addWidget(self._build_input_group())
        left_column.addWidget(self._build_export_group())
        left_column.addStretch(1)

        top_row.addLayout(left_column, 0)
        top_row.addWidget(self._build_preview_group(), 1)

        layout.addLayout(top_row, 1)
        self.setCentralWidget(root)

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("Input")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        button_row = QHBoxLayout()
        self.open_folder_button = QPushButton("Open Folder")
        self.add_files_button = QPushButton("Add Files")
        self.open_folder_button.clicked.connect(self._choose_folder)
        self.add_files_button.clicked.connect(self._choose_files)
        button_row.addWidget(self.open_folder_button)
        button_row.addWidget(self.add_files_button)
        layout.addLayout(button_row)

        self.sequence_name_label = QLabel("No sequence selected.")
        self.sequence_name_label.setObjectName("sequenceName")
        self.sequence_name_label.setWordWrap(True)
        layout.addWidget(self.sequence_name_label)

        self.sequence_details_label = QLabel("")
        self.sequence_details_label.setWordWrap(True)
        layout.addWidget(self.sequence_details_label)

        return group

    def _build_preview_group(self) -> QGroupBox:
        group = QGroupBox("Preview")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.preview_label = PreviewLabel()
        self.preview_label.setText("Load a sequence to preview the first frame.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(420, 240)
        self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_label.setObjectName("previewPanel")
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label, 1)

        slider_row = QHBoxLayout()
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.valueChanged.connect(self._frame_changed)
        self.frame_label = QLabel("Frame 0 / 0")
        slider_row.addWidget(self.frame_slider, 1)
        slider_row.addWidget(self.frame_label)
        layout.addLayout(slider_row)

        return group

    def _build_export_group(self) -> QGroupBox:
        group = QGroupBox("Export")
        self.export_group = group
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.export_form = QFormLayout()
        self.export_form.setSpacing(10)

        self.scale_percent_spin = QSpinBox()
        self.scale_percent_spin.setRange(1, 1000)
        self.scale_percent_spin.setSuffix("%")
        self.scale_percent_spin.setValue(100)
        self.scale_percent_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.scale_percent_spin.valueChanged.connect(self._update_output_size_label)
        self.export_form.addRow("Size", self.scale_percent_spin)

        self.output_size_label = QLabel("Output size: -")
        self.output_size_label.setObjectName("outputSizeLabel")
        self.output_size_label.setWordWrap(False)
        self.export_form.addRow("", self.output_size_label)

        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.1, 120.0)
        self.fps_spin.setDecimals(2)
        self.fps_spin.setValue(24.0)
        self.fps_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.export_form.addRow("FPS", self.fps_spin)

        self.loop_mode_combo = QComboBox()
        self.loop_mode_combo.addItems(["Infinite", "Fixed", "No Loop"])
        self.loop_mode_combo.currentTextChanged.connect(self._loop_mode_changed)
        self.export_form.addRow("Loop mode", self.loop_mode_combo)

        self.loop_fixed_spin = QSpinBox()
        self.loop_fixed_spin.setRange(1, 9999)
        self.loop_fixed_spin.setValue(1)
        self.loop_fixed_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.loop_fixed_spin.hide()
        self.export_form.addRow("Loop count", self.loop_fixed_spin)
        self.loop_count_label = self.export_form.labelForField(self.loop_fixed_spin)
        if self.loop_count_label is not None:
            self.loop_count_label.hide()

        self.transparency_checkbox = QCheckBox("Use GIF transparency")
        self.transparency_checkbox.setChecked(True)
        self.transparency_checkbox.toggled.connect(self._transparency_toggled)
        self.transparency_checkbox.toggled.connect(lambda _: self._refresh_preview())
        self.export_form.addRow("", self.transparency_checkbox)

        self.alpha_threshold_spin = QSpinBox()
        self.alpha_threshold_spin.setRange(0, 255)
        self.alpha_threshold_spin.setValue(10)
        self.alpha_threshold_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.alpha_threshold_spin.valueChanged.connect(lambda _: self._refresh_preview())
        self.export_form.addRow("Alpha threshold", self.alpha_threshold_spin)

        self.matte_button = QPushButton()
        self.matte_button.setObjectName("matteColorButton")
        self.matte_button.setFixedHeight(34)
        self.matte_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.matte_button.clicked.connect(self._choose_matte_color)
        self.export_form.addRow("Matte color", self.matte_button)

        self.dither_checkbox = QCheckBox("Enable dithering")
        self.dither_checkbox.setChecked(True)
        self.dither_checkbox.setToolTip(
            "Adds a fine pixel pattern when reducing the image to GIF's limited color palette."
        )
        self.export_form.addRow("", self.dither_checkbox)

        layout.addLayout(self.export_form)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose an output GIF file...")
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self._choose_output)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(output_browse)
        layout.addLayout(output_row)

        self.export_button = QPushButton("Export GIF")
        self.export_button.clicked.connect(self._export_gif)
        layout.addWidget(self.export_button)

        return group

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #121216;
                color: #e7ecf3;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            QLabel {
                background: transparent;
            }
            QMainWindow {
                background: #121216;
            }
            QLabel#headerTitle {
                font-size: 28px;
                font-weight: 700;
                color: #f7fafc;
            }
            QLabel#sequenceName {
                font-size: 15px;
                font-weight: 700;
                color: #c9e1ff;
            }
            QLabel#outputSizeLabel {
                color: #8c94a3;
                font-size: 12px;
            }
            QLabel#outputSizeLabel:disabled {
                color: #5d6572;
            }
            QGroupBox {
                border: 1px solid #303642;
                border-radius: 12px;
                margin-top: 12px;
                padding: 14px;
                background: #181d26;
                font-weight: 600;
            }
            QGroupBox[sequenceLoaded="false"] {
                color: #7f8897;
                border: 1px solid #252b35;
                background: #141920;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                background: transparent;
            }
            QGroupBox[sequenceLoaded="false"]::title {
                color: #7f8897;
                background: transparent;
            }
            QLabel#previewPanel {
                border-radius: 14px;
                background: #0f131a;
                border: 1px solid #2f3744;
                padding: 12px;
            }
            QPushButton {
                background: #2d6df6;
                border: none;
                border-radius: 10px;
                padding: 9px 14px;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3f7cf9;
            }
            QPushButton:disabled {
                background: #2c323d;
                color: #7f8897;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #0f131a;
                border: 1px solid #2f3744;
                border-radius: 10px;
                padding: 7px 10px;
                min-height: 20px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                background: transparent;
            }
            QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
                background: #161b22;
                color: #6b7484;
                border: 1px solid #252b35;
            }
            QComboBox QAbstractItemView {
                background: #121821;
                color: #e7ecf3;
                border: 1px solid #2f3744;
                outline: 0;
                selection-background-color: #24344b;
                selection-color: #f5f8fc;
            }
            QComboBox QAbstractItemView::item {
                min-height: 24px;
                padding: 4px 8px;
                background: transparent;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #24344b;
                color: #f5f8fc;
                border: none;
                outline: 0;
            }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
                width: 0px;
                border: none;
                background: transparent;
            }
            QSlider {
                background: transparent;
                min-height: 24px;
            }
            QSlider::groove:horizontal {
                border-radius: 6px;
                background: #2f3744;
                height: 8px;
            }
            QSlider::handle:horizontal {
                background: #8bc1ff;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QCheckBox {
                background: transparent;
                spacing: 8px;
            }
            QCheckBox:disabled {
                color: #697283;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 2px solid #f3f7fb;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4d94ff;
                background: #4d94ff;
            }
            QCheckBox::indicator:disabled {
                border: 2px solid #596273;
                background: transparent;
            }
            QCheckBox::indicator:checked:disabled {
                border: 2px solid #47627f;
                background: #47627f;
            }
            """
        )

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose sequence folder")
        if not folder:
            return
        sequence_groups = detect_sequences(Path(folder))
        if not sequence_groups:
            self._show_warning("No supported frames found", "The selected folder does not contain JPG, PNG, or EXR images.")
            return
        self._load_sequence(choose_primary_sequence(sequence_groups), source_folder=Path(folder), detected_group_count=len(sequence_groups))

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose image sequence files",
            filter="Images (*.jpg *.jpeg *.png *.exr)",
        )
        if not files:
            return
        group = group_selected_files([Path(file) for file in files])
        self._load_sequence(group, source_folder=None, detected_group_count=1)

    def _load_sequence(
        self,
        group: SequenceGroup,
        source_folder: Path | None,
        detected_group_count: int,
    ) -> None:
        self.loaded_sequence = LoadedSequence(group=group, source_folder=source_folder)
        self.detected_group_count = detected_group_count
        self._update_controls_enabled(True)
        self.frame_slider.blockSignals(True)
        self.frame_slider.setMaximum(max(0, len(group.paths) - 1))
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)

        try:
            first_frame = load_rgba_frame(group.paths[0])
        except Exception as error:  # noqa: BLE001
            self._show_warning("Could not load first frame", str(error))
            return
        height, width = first_frame.shape[:2]
        self.current_frame_rgba = first_frame
        self.source_width = width
        self.source_height = height
        self.source_aspect_ratio = width / max(height, 1)
        self.preview_label.set_aspect_ratio(width, height)
        self.scale_percent_spin.setValue(100)
        self._update_output_size_label()
        self._loop_mode_changed(self.loop_mode_combo.currentText())
        self._refresh_preview()
        self._update_sequence_details()
        self._suggest_output_path()

    def _update_sequence_details(self) -> None:
        if not self.loaded_sequence:
            self.sequence_name_label.setText("No sequence selected.")
            self.sequence_details_label.setText("")
            return
        group = self.loaded_sequence.group
        first_path = group.paths[0]
        self.sequence_name_label.setText(group.name)
        details = [
            f"{len(group.paths)} frame(s)",
            f"Starts with: {first_path.name}",
            f"Source size: {self.source_width} x {self.source_height}",
        ]
        if group.first_frame is not None and group.last_frame is not None:
            details.append(f"Range: {group.first_frame} to {group.last_frame}")
        if self.loaded_sequence.source_folder:
            details.append(f"Folder: {self.loaded_sequence.source_folder}")
        if self.detected_group_count > 1:
            details.append(f"Detected {self.detected_group_count} sequences, loaded the largest one")
        self.sequence_details_label.setText(" | ".join(details))

    def _frame_changed(self, value: int) -> None:
        if not self.loaded_sequence:
            return
        path = self.loaded_sequence.group.paths[value]
        try:
            self.current_frame_rgba = load_rgba_frame(path)
        except Exception as error:  # noqa: BLE001
            self._show_warning("Could not load frame", str(error))
            return
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self.current_frame_rgba is None:
            self.preview_label.setText("Load a sequence to preview the first frame.")
            self.frame_label.setText("Frame 0 / 0")
            return
        image = render_preview_frame(
            self.current_frame_rgba,
            preview_size=(
                max(1, self.preview_label.contentsRect().width()),
                max(1, self.preview_label.contentsRect().height()),
            ),
            matte_color=self.current_matte_color,
            use_transparency=self.transparency_checkbox.isChecked(),
            alpha_threshold=self.alpha_threshold_spin.value(),
        )
        qimage = self._pil_to_qimage(image)
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        current = self.frame_slider.value() + 1
        total = self.frame_slider.maximum() + 1
        self.frame_label.setText(f"Frame {current} / {total}")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_preview()

    def _pil_to_qimage(self, image) -> QImage:
        rgba = image.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        return QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888).copy()

    def _transparency_toggled(self, checked: bool) -> None:
        self.alpha_threshold_spin.setEnabled(checked)

    def _loop_mode_changed(self, mode: str) -> None:
        is_fixed = mode == "Fixed"
        self.loop_fixed_spin.setVisible(is_fixed)
        if self.loop_count_label is not None:
            self.loop_count_label.setVisible(is_fixed)

    def _choose_matte_color(self) -> None:
        current = QColor(*self.current_matte_color)
        selected = QColorDialog.getColor(
            current,
            self,
            "Choose matte color",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if not selected.isValid():
            return
        self.current_matte_color = (selected.red(), selected.green(), selected.blue())
        self._update_matte_button()
        self._refresh_preview()

    def _update_matte_button(self) -> None:
        r, g, b = self.current_matte_color
        self.matte_button.setText(f"{r}, {g}, {b}")
        self.matte_button.setStyleSheet(
            "QPushButton {"
            "border-radius: 10px;"
            "padding: 7px 12px;"
            "font-weight: 600;"
            f"background: rgb({r}, {g}, {b});"
            f"color: {'#101214' if QColor(r, g, b).lightness() > 128 else '#f3f7fb'};"
            "border: 1px solid #4b5563;"
            "}"
            "QPushButton:disabled {"
            "background: #2c323d;"
            "color: #7f8897;"
            "border: 1px solid #252b35;"
            "}"
        )

    def _scaled_output_size(self) -> tuple[int, int]:
        scale = self.scale_percent_spin.value() / 100.0
        width = max(1, round(self.source_width * scale))
        height = max(1, round(self.source_height * scale))
        return width, height

    def _update_output_size_label(self) -> None:
        if not self.loaded_sequence or self.source_width <= 0 or self.source_height <= 0:
            self.output_size_label.setText("-")
            return
        width, height = self._scaled_output_size()
        self.output_size_label.setText(f"{width} x {height} px")

    def _choose_output(self) -> None:
        suggested = self.output_edit.text() or "output.gif"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Choose GIF output",
            suggested,
            "GIF Files (*.gif)",
        )
        if file_name:
            self.output_edit.setText(file_name)

    def _suggest_output_path(self) -> None:
        if not self.loaded_sequence:
            return
        first = self.loaded_sequence.group.paths[0]
        if self.loaded_sequence.source_folder:
            suggested = self.loaded_sequence.source_folder / f"{first.stem.rsplit('_', 1)[0] if '_' in first.stem else first.stem}.gif"
        else:
            suggested = first.with_suffix(".gif")
        self.output_edit.setText(str(suggested))

    def _collect_export_settings(self) -> ExportSettings:
        width, height = self._scaled_output_size()
        loop_mode = self.loop_mode_combo.currentText()
        loop_count: int | None
        if loop_mode == "Infinite":
            loop_count = 0
        elif loop_mode == "Fixed":
            loop_count = self.loop_fixed_spin.value()
        else:
            loop_count = None
        return ExportSettings(
            width=width,
            height=height,
            fps=self.fps_spin.value(),
            use_transparency=self.transparency_checkbox.isChecked(),
            matte_color=self.current_matte_color,
            dither=self.dither_checkbox.isChecked(),
            alpha_threshold=self.alpha_threshold_spin.value(),
            loop_count=loop_count,
        )

    def _export_gif(self) -> None:
        if not self.loaded_sequence:
            self._show_warning("No sequence loaded", "Choose a folder or image files before exporting.")
            return
        output_text = self.output_edit.text().strip()
        if not output_text:
            self._show_warning("Missing output path", "Choose where the GIF should be written.")
            return

        output_path = Path(output_text)
        settings = self._collect_export_settings()
        try:
            self.export_button.setEnabled(False)
            self.export_button.setText("Exporting...")
            save_gif(self.loaded_sequence.group.paths, output_path, settings)
        except Exception as error:  # noqa: BLE001
            self._show_warning("Export failed", str(error))
        else:
            QMessageBox.information(
                self,
                "Export complete",
                f"GIF exported successfully to:\n{output_path}",
            )
        finally:
            self.export_button.setEnabled(True)
            self.export_button.setText("Export GIF")

    def _update_controls_enabled(self, enabled: bool) -> None:
        self.export_group.setProperty("sequenceLoaded", enabled)
        self.export_group.style().unpolish(self.export_group)
        self.export_group.style().polish(self.export_group)
        self.export_group.update()
        for widget in (
            self.frame_slider,
            self.scale_percent_spin,
            self.fps_spin,
            self.loop_mode_combo,
            self.loop_fixed_spin,
            self.transparency_checkbox,
            self.alpha_threshold_spin,
            self.matte_button,
            self.dither_checkbox,
            self.output_edit,
            self.export_button,
        ):
            widget.setEnabled(enabled)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
