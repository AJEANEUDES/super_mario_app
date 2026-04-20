"""
Batch Predict Widget - Prédiction YOLO par lot sur un niveau

Widget autonome : logique métier + interface dans le même fichier.
Compatible mode clair ET mode sombre.

Version 1.2.0 - Refactor layout : ScrollArea + proportions corrigées
Fichier: ui/batch_predict_widget.py
"""

import os
import re
import platform
import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QGridLayout,
    QProgressBar, QLineEdit, QCheckBox, QDoubleSpinBox, QSpinBox,
    QTextEdit, QSplitter, QComboBox, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont


# ══════════════════════════════════════════════════════════════════════════════
#  Thread de travail
# ══════════════════════════════════════════════════════════════════════════════

class _PredictWorker(QThread):
    sig_log      = pyqtSignal(str)
    sig_progress = pyqtSignal(int, int)
    sig_done     = pyqtSignal(bool, str, int, int, str)

    def __init__(self, params: dict):
        super().__init__()
        self._p      = params
        self._proc: Optional[subprocess.Popen] = None
        self._cancel = False

    def request_cancel(self):
        self._cancel = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def run(self):
        p = self._p

        if not os.path.isfile(p["model"]):
            self.sig_done.emit(False, f"Modèle introuvable:\n{p['model']}", 0, 0, "")
            return
        if not os.path.isdir(p["source"]):
            self.sig_done.emit(False, f"Dossier source introuvable:\n{p['source']}", 0, 0, "")
            return

        total = self._count_images(p["source"])
        if total == 0:
            self.sig_done.emit(False, "Aucune image trouvée dans le dossier source.", 0, 0, "")
            return

        self.sig_log.emit(f"🖼️  Images à traiter : {total}")
        self.sig_log.emit(f"🤖 Modèle           : {p['model']}")
        self.sig_log.emit(f"📁 Source           : {p['source']}")
        self.sig_log.emit(f"📤 Sortie           : {p['output']}/{p['name']}")
        self.sig_log.emit(f"🎯 Confidence={p['conf']}  IOU={p['iou']}  imgsz={p['imgsz']}")
        self.sig_log.emit("")

        cmd = [
            "yolo", "predict",
            f"model={p['model']}", f"source={p['source']}",
            f"conf={p['conf']}", f"iou={p['iou']}", f"imgsz={p['imgsz']}",
            f"project={p['output']}", f"name={p['name']}",
            f"save_txt={str(p['save_txt']).lower()}",
            f"save_conf={str(p['save_conf']).lower()}",
            f"save_crop={str(p['save_crop']).lower()}",
            "exist_ok=True",
        ]
        if p.get("device"):
            cmd.append(f"device={p['device']}")

        self.sig_log.emit("▶️  " + " ".join(cmd))
        self.sig_log.emit("")

        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except FileNotFoundError:
            self.sig_done.emit(False,
                "Commande 'yolo' introuvable.\n"
                "Installez ultralytics : pip install ultralytics",
                0, 0, "")
            return

        current = 0
        for raw in self._proc.stdout:
            if self._cancel:
                break
            line = raw.rstrip()
            if not line:
                continue
            self.sig_log.emit(line)
            m = re.search(r'image\s+(\d+)/(\d+)', line)
            if m:
                current = int(m.group(1))
                total   = int(m.group(2))
                self.sig_progress.emit(current, total)

        self._proc.wait()
        ret = self._proc.returncode

        if self._cancel:
            self.sig_done.emit(False, "Prédiction annulée.", current, 0, "")
            return

        out_path = os.path.join(p["output"], p["name"])
        if not os.path.isdir(out_path):
            candidates = sorted(Path(p["output"]).glob(f"{p['name']}*"), reverse=True)
            if candidates:
                out_path = str(candidates[0])

        detections = 0
        labels_dir = os.path.join(out_path, "labels")
        if os.path.isdir(labels_dir):
            detections = sum(
                1 for f in Path(labels_dir).glob("*.txt") if f.stat().st_size > 0
            )

        if ret == 0:
            self.sig_log.emit("")
            self.sig_log.emit(f"✅ Terminé — {detections}/{total} images avec détections")
            self.sig_log.emit(f"📂 Résultats : {out_path}")
            self.sig_done.emit(True, "Prédiction terminée avec succès!",
                               total, detections, out_path)
        else:
            self.sig_done.emit(False, f"YOLO code d'erreur {ret}.",
                               current, detections, out_path)

    @staticmethod
    def _count_images(folder: str) -> int:
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        return sum(1 for _, _, files in os.walk(folder)
                   for f in files if Path(f).suffix.lower() in exts)


# ══════════════════════════════════════════════════════════════════════════════
#  Widget principal
# ══════════════════════════════════════════════════════════════════════════════

class BatchPredictWidget(QWidget):

    _C_CYAN   = "#0097a7"
    _C_AMBER  = "#e65100"
    _C_GREEN  = "#2e7d32"
    _C_RED    = "#c62828"
    _C_PURPLE = "#6a1b9a"
    _C_BLUE   = "#1565c0"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[_PredictWorker] = None
        self._result_path = ""
        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════
    #  Layout principal
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # ── Titre ──────────────────────────────────────────────────────
        title = QLabel("🤖 Prédiction YOLO par lot")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self._C_CYAN};")
        root.addWidget(title)

        desc = QLabel(
            "Sélectionnez un modèle entraîné et un dossier source "
            "(niveau brut ou augmenté). YOLO génère les prédictions "
            "et sauvegarde les labels .txt."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-style: italic; color: #888;")
        root.addWidget(desc)

        # ── Splitter principal ─────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)

        # Panneau gauche avec ScrollArea
        splitter.addWidget(self._build_left_panel())
        # Panneau droit
        splitter.addWidget(self._build_right_panel())

        # 45 % gauche / 55 % droite
        splitter.setStretchFactor(0, 45)
        splitter.setStretchFactor(1, 55)

        root.addWidget(splitter, stretch=1)

        # ── Boutons d'action ───────────────────────────────────────────
        root.addWidget(self._build_action_bar())

    # ── Panneau gauche ────────────────────────────────────────────────────

    def _build_left_panel(self) -> QScrollArea:
        """Tous les groupes de configuration dans une ScrollArea."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(4, 4, 8, 4)
        lay.setSpacing(12)

        lay.addWidget(self._grp_model())
        lay.addWidget(self._grp_source())
        lay.addWidget(self._grp_params())
        lay.addWidget(self._grp_options())
        lay.addStretch()

        scroll.setWidget(container)
        return scroll

    # ── Panneau droit ─────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 4, 4, 4)
        lay.setSpacing(10)

        lay.addWidget(self._grp_progress())
        lay.addWidget(self._grp_logs(), stretch=1)
        lay.addWidget(self._grp_stats())

        return panel

    # ══════════════════════════════════════════════════════════════════════
    #  Groupes de configuration
    # ══════════════════════════════════════════════════════════════════════

    def _grp_model(self) -> QGroupBox:
        grp = QGroupBox("🤖 Modèle YOLO (best.pt)")
        grp.setStyleSheet(self._gbstyle(self._C_CYAN))
        lay = QGridLayout(grp)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 18, 12, 12)
        lay.setColumnStretch(1, 1)

        lay.addWidget(self._lbl("Fichier modèle :"), 0, 0)
        self.ed_model = QLineEdit()
        self.ed_model.setPlaceholderText("Chemin vers best.pt ...")
        self.ed_model.setMinimumHeight(34)
        lay.addWidget(self.ed_model, 0, 1)
        btn_b = self._small_btn("📂")
        btn_b.clicked.connect(self._browse_model)
        lay.addWidget(btn_b, 0, 2)

        btn_auto = QPushButton("🔍 Trouver automatiquement")
        btn_auto.setMinimumHeight(36)
        btn_auto.setStyleSheet(
            f"QPushButton {{ background-color:{self._C_BLUE}; color:white; "
            f"border:none; border-radius:5px; font-size:12px; font-weight:bold; }}"
            f"QPushButton:hover {{ background-color:#1976D2; }}"
        )
        btn_auto.clicked.connect(self._auto_find_model)
        lay.addWidget(btn_auto, 1, 0, 1, 3)

        return grp

    def _grp_source(self) -> QGroupBox:
        grp = QGroupBox("📁 Source et Sortie")
        grp.setStyleSheet(self._gbstyle(self._C_AMBER))
        lay = QGridLayout(grp)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 18, 12, 12)
        lay.setColumnStretch(1, 1)

        # Dossier images
        lay.addWidget(self._lbl("Dossier images :"), 0, 0)
        self.ed_source = QLineEdit()
        self.ed_source.setPlaceholderText(
            "Ex : augmented_dataset/images   ou   classified_levels/level_1-1"
        )
        self.ed_source.setMinimumHeight(34)
        self.ed_source.textChanged.connect(self._on_source_changed)
        lay.addWidget(self.ed_source, 0, 1)
        btn_src = self._small_btn("📂")
        btn_src.clicked.connect(lambda: self._browse_dir(self.ed_source))
        lay.addWidget(btn_src, 0, 2)

        self.lbl_count = QLabel("Aucun dossier sélectionné")
        self.lbl_count.setStyleSheet("font-size: 11px; font-style: italic; color: #888;")
        lay.addWidget(self.lbl_count, 1, 0, 1, 3)

        # Dossier de sortie
        lay.addWidget(self._lbl("Dossier de sortie :"), 2, 0)
        self.ed_output = QLineEdit("predictions")
        self.ed_output.setMinimumHeight(34)
        lay.addWidget(self.ed_output, 2, 1)
        btn_out = self._small_btn("📂")
        btn_out.clicked.connect(lambda: self._browse_dir(self.ed_output))
        lay.addWidget(btn_out, 2, 2)

        # Nom du run
        lay.addWidget(self._lbl("Nom du run :"), 3, 0)
        self.ed_run = QLineEdit("predict_run")
        self.ed_run.setMinimumHeight(34)
        lay.addWidget(self.ed_run, 3, 1, 1, 2)

        return grp

    def _grp_params(self) -> QGroupBox:
        grp = QGroupBox("⚙️ Paramètres YOLO")
        grp.setStyleSheet(self._gbstyle("#bf6000"))
        lay = QGridLayout(grp)
        lay.setSpacing(12)
        lay.setContentsMargins(12, 18, 12, 12)
        lay.setColumnStretch(1, 1)

        # Confidence
        lay.addWidget(self._lbl("Confidence :"), 0, 0)
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.01, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setDecimals(2)
        self.spin_conf.setValue(0.25)
        self.spin_conf.setMinimumHeight(34)
        self.spin_conf.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self.spin_conf, 0, 1)

        # IOU
        lay.addWidget(self._lbl("Seuil IOU :"), 1, 0)
        self.spin_iou = QDoubleSpinBox()
        self.spin_iou.setRange(0.01, 1.0)
        self.spin_iou.setSingleStep(0.05)
        self.spin_iou.setDecimals(2)
        self.spin_iou.setValue(0.45)
        self.spin_iou.setMinimumHeight(34)
        self.spin_iou.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self.spin_iou, 1, 1)

        # Image size
        lay.addWidget(self._lbl("Taille image (imgsz) :"), 2, 0)
        self.spin_imgsz = QSpinBox()
        self.spin_imgsz.setRange(32, 1280)
        self.spin_imgsz.setSingleStep(32)
        self.spin_imgsz.setValue(640)
        self.spin_imgsz.setMinimumHeight(34)
        self.spin_imgsz.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self.spin_imgsz, 2, 1)

        # Device
        lay.addWidget(self._lbl("Device :"), 3, 0)
        self.combo_device = QComboBox()
        self.combo_device.addItems(["auto (CPU/GPU)", "cpu", "0", "1", "mps"])
        self.combo_device.setMinimumHeight(34)
        lay.addWidget(self.combo_device, 3, 1)

        return grp

    def _grp_options(self) -> QGroupBox:
        grp = QGroupBox("🔧 Options de sauvegarde")
        grp.setStyleSheet(self._gbstyle(self._C_PURPLE))
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 18, 12, 12)

        self.chk_save_txt  = QCheckBox("💾 Sauvegarder les labels .txt (YOLO)")
        self.chk_save_conf = QCheckBox("📊 Inclure la confidence dans les .txt")
        self.chk_save_crop = QCheckBox("✂️  Sauvegarder les crops des détections")

        self.chk_save_txt.setChecked(True)
        self.chk_save_conf.setChecked(True)
        self.chk_save_crop.setChecked(False)

        for cb in (self.chk_save_txt, self.chk_save_conf, self.chk_save_crop):
            cb.setMinimumHeight(28)
            lay.addWidget(cb)

        return grp

    # ══════════════════════════════════════════════════════════════════════
    #  Groupes droits
    # ══════════════════════════════════════════════════════════════════════

    def _grp_progress(self) -> QGroupBox:
        grp = QGroupBox("📊 Progression")
        grp.setStyleSheet(self._gbstyle(self._C_GREEN))
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 18, 12, 12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {self._C_CYAN};
                border-radius: 6px;
                text-align: center;
                font-weight: bold;
                font-size: 12px;
            }}
            QProgressBar::chunk {{
                background-color: {self._C_CYAN};
                border-radius: 4px;
            }}
        """)
        lay.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("En attente...")
        self.lbl_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_progress.setStyleSheet("font-size: 12px; color: #888;")
        lay.addWidget(self.lbl_progress)

        return grp

    def _grp_logs(self) -> QGroupBox:
        grp = QGroupBox("📋 Logs YOLO")
        grp.setStyleSheet(self._gbstyle(self._C_BLUE))
        lay = QVBoxLayout(grp)
        lay.setSpacing(6)
        lay.setContentsMargins(12, 18, 12, 12)

        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 6px;
            }
        """)
        lay.addWidget(self.logs, stretch=1)

        btn_clear = QPushButton("🗑️ Vider les logs")
        btn_clear.setMinimumHeight(30)
        btn_clear.clicked.connect(self.logs.clear)
        lay.addWidget(btn_clear)

        return grp

    def _grp_stats(self) -> QGroupBox:
        grp = QGroupBox("📈 Résultats")
        grp.setStyleSheet(self._gbstyle(self._C_AMBER))
        lay = QGridLayout(grp)
        lay.setSpacing(6)
        lay.setContentsMargins(12, 18, 12, 12)

        self.stat_total = QLabel("—")
        self.stat_total.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.stat_total.setStyleSheet(f"color: {self._C_CYAN};")
        self.stat_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.stat_total, 0, 0)

        self.stat_det = QLabel("—")
        self.stat_det.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.stat_det.setStyleSheet(f"color: {self._C_CYAN};")
        self.stat_det.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.stat_det, 0, 1)

        for col, text in enumerate(("Images traitées", "Avec détections")):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; color: #888;")
            lay.addWidget(lbl, 1, col)

        return grp

    # ══════════════════════════════════════════════════════════════════════
    #  Barre d'actions
    # ══════════════════════════════════════════════════════════════════════

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(12)

        self.btn_start = QPushButton("▶️ Lancer la prédiction")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.setStyleSheet(self._btn_style(self._C_CYAN, "#00acc1", fg="#000"))
        self.btn_start.clicked.connect(self._start)
        lay.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("⏹️ Annuler")
        self.btn_cancel.setMinimumHeight(50)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet(self._btn_style(self._C_RED, "#d32f2f"))
        self.btn_cancel.clicked.connect(self._cancel)
        lay.addWidget(self.btn_cancel)

        self.btn_open = QPushButton("📂 Ouvrir les résultats")
        self.btn_open.setMinimumHeight(50)
        self.btn_open.setStyleSheet(self._btn_style(self._C_AMBER, "#f57c00"))
        self.btn_open.clicked.connect(self._open_results)
        lay.addWidget(self.btn_open)

        return bar

    # ══════════════════════════════════════════════════════════════════════
    #  Slots
    # ══════════════════════════════════════════════════════════════════════

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner le modèle", "",
            "Modèles YOLO (*.pt);;Tous (*)"
        )
        if path:
            self.ed_model.setText(path)

    def _browse_dir(self, edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            edit.setText(folder)

    def _auto_find_model(self):
        roots = [".", "runs", "runs/detect", "runs/detect/train",
                 "runs/detect/train/weights", "final_mario_dataset",
                 "training_output", "models"]
        found = []
        for root in roots:
            if os.path.isdir(root):
                found.extend(str(p) for p in Path(root).rglob("best.pt"))

        if not found:
            QMessageBox.information(self, "Modèle non trouvé",
                "Aucun fichier best.pt trouvé automatiquement.\n\n"
                "Chemin typique :\n  runs/detect/train/weights/best.pt")
            return

        best = max(found, key=lambda p: Path(p).stat().st_mtime)
        self.ed_model.setText(best)
        self._log(f"✅ Modèle sélectionné : {best}")
        if len(found) > 1:
            self._log(f"   ({len(found)} candidats trouvés, le plus récent retenu)")

    def _on_source_changed(self, text: str):
        if not text or not os.path.isdir(text):
            self.lbl_count.setText("Dossier invalide ou introuvable")
            self.lbl_count.setStyleSheet(f"color: {self._C_RED}; font-size: 11px;")
            return
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        n = sum(1 for _, _, files in os.walk(text)
                for f in files if Path(f).suffix.lower() in exts)
        self.lbl_count.setText(f"✅ {n} image(s) détectée(s) dans ce dossier")
        self.lbl_count.setStyleSheet(
            f"color: {self._C_GREEN}; font-size: 11px; font-weight: bold;"
        )
        proposed = Path(text).name + "_predict"
        if self.ed_run.text() in ("", "predict_run"):
            self.ed_run.setText(proposed)

    def _validate(self) -> bool:
        if not self.ed_model.text() or not os.path.isfile(self.ed_model.text()):
            QMessageBox.warning(self, "Modèle manquant",
                "Sélectionnez un fichier modèle YOLO valide (.pt).")
            return False
        if not self.ed_source.text() or not os.path.isdir(self.ed_source.text()):
            QMessageBox.warning(self, "Source manquante",
                "Sélectionnez un dossier source contenant des images.")
            return False
        if not self.ed_output.text():
            QMessageBox.warning(self, "Sortie manquante",
                "Indiquez un dossier de sortie.")
            return False
        return True

    def _start(self):
        if not self._validate():
            return

        dev_text = self.combo_device.currentText()
        device   = "" if dev_text.startswith("auto") else dev_text

        params = dict(
            model     = self.ed_model.text().strip(),
            source    = self.ed_source.text().strip(),
            output    = self.ed_output.text().strip(),
            name      = self.ed_run.text().strip() or "predict_run",
            conf      = self.spin_conf.value(),
            iou       = self.spin_iou.value(),
            imgsz     = self.spin_imgsz.value(),
            device    = device,
            save_txt  = self.chk_save_txt.isChecked(),
            save_conf = self.chk_save_conf.isChecked(),
            save_crop = self.chk_save_crop.isChecked(),
        )

        self._log("=" * 60)
        self._log("▶️  Démarrage de la prédiction YOLO...")
        self._log("")

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_progress.setText("Initialisation...")
        self.stat_total.setText("—")
        self.stat_det.setText("—")

        self._worker = _PredictWorker(params)
        self._worker.sig_log.connect(self._log)
        self._worker.sig_progress.connect(self._on_progress)
        self._worker.sig_done.connect(self._on_done)
        self._worker.start()

    def _cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._log("⏹️ Annulation demandée...")

    def _on_progress(self, current: int, total: int):
        if total > 0:
            pct = int(current * 100 / total)
            self.progress_bar.setValue(pct)
            self.lbl_progress.setText(f"{current} / {total}  ({pct}%)")

    def _on_done(self, success: bool, message: str,
                 processed: int, detections: int, out_path: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self._result_path = out_path
        self.stat_total.setText(str(processed))
        self.stat_det.setText(str(detections))

        if success:
            self.progress_bar.setValue(100)
            self.lbl_progress.setText(f"Terminé — {processed} images traitées")
            QMessageBox.information(self, "✅ Terminé",
                f"{message}\n\n"
                f"• Images traitées   : {processed}\n"
                f"• Avec détections   : {detections}\n"
                f"• Résultats dans    : {out_path}")
        else:
            self.lbl_progress.setText("Échec")
            QMessageBox.warning(self, "❌ Erreur", message)

        self._worker = None

    def _open_results(self):
        path = self._result_path or self.ed_output.text()
        if path and os.path.isdir(path):
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        else:
            QMessageBox.warning(self, "Dossier introuvable",
                "Le dossier n'existe pas encore.\nLancez d'abord une prédiction.")

    def _log(self, msg: str):
        self.logs.append(msg)
        self.logs.verticalScrollBar().setValue(
            self.logs.verticalScrollBar().maximum()
        )

    # ══════════════════════════════════════════════════════════════════════
    #  Helpers de style
    # ══════════════════════════════════════════════════════════════════════

    def _gbstyle(self, color: str) -> str:
        return (
            f"QGroupBox {{ font-weight:bold; font-size:13px; color:{color}; "
            f"border:2px solid {color}; border-radius:8px; "
            f"margin-top:14px; padding-top:14px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 8px; }}"
        )

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px;")
        return lbl

    def _small_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(36, 34)
        return btn

    def _btn_style(self, bg: str, hover: str, fg: str = "#fff") -> str:
        return (
            f"QPushButton {{ background-color:{bg}; color:{fg}; border:none; "
            f"border-radius:6px; font-size:14px; font-weight:bold; padding:12px 28px; }}"
            f"QPushButton:hover {{ background-color:{hover}; }}"
            f"QPushButton:pressed {{ opacity:0.8; }}"
            f"QPushButton:disabled {{ background-color:#aaa; color:#eee; }}"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Test standalone
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = BatchPredictWidget()
    w.setWindowTitle("Batch Predict — Test")
    w.resize(1200, 850)
    w.show()
    sys.exit(app.exec())