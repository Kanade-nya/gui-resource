from __future__ import annotations

import monotonic_align.core
import platform
import logging
import random
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import soundfile as sf
import torch
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSlider, QTextEdit, QVBoxLayout, QWidget)

import commons
import utils
from models import SynthesizerTrn
from text import transform
from text.cleaners import (japanese_cleaners, japanese_cleaners2,
                           japanese_tokenization_cleaners)

logger = logging.getLogger("PJSK-MultiGUI")
# 设置日志等级
logger.setLevel(logging.DEBUG)
# 追加写入文件a ，设置utf-8编码防止中文写入乱码
if platform.system() == "Darwin":
    log_dir = Path.home() / "Library/Logs/PJSK-MultiGUI"
else:
    log_dir = Path.home() / "PJSK-MultiGUI/logs"
log_dir.mkdir(parents=True, exist_ok=True)
handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
# 向文件输出的日志信息格式
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
)
# 加载文件到logger对象中
logger.addHandler(handler)


@dataclass(frozen=True)
class SymbolPreset:
    id: int
    symbols: List[str]


SYMBOL_PRESETS: Dict[str, SymbolPreset] = {
    "default": SymbolPreset(1, list(' !"&*,-.?ABCINU[]abcdefghijklmnoprstuwyz{}~')),
    "preset2": SymbolPreset(2, [
        "_", *list(",.!?-"),
        *list("AEINOQUabdefghijkmnoprstuvwyzʃʧ↓↑ ")]),
    "preset3": SymbolPreset(3, [
        "_", *list(",.!?-~…"),
        *list("AEINOQUabdefghijkmnoprstuvwyzʃʧʦ↓↑ ")]),
    "ipa": SymbolPreset(4, [
        "_", *list(";:,.!?¡¿—…\"«»“” "),
        *list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
        *list("ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲʷˠˤ˞↓↑→↗↘'̩'ᵻ")]),
}

CONFIG_TO_PRESET = {
    "mmj.json": "default",
    "vbs.json": "default",
    "ws.json": "default",
    "mafuyu.json": "default",
}

MULTI_SPK_GROUPS = {
    "mmj.json": ["minori", "haruka", "airi", "shizuku"],
    "vbs.json": ["akito", "an", "kohane", "toya"],
    "ws.json": ["emu", "nene", "rui", "tsukasa"],
    "mafuyu.json": ["white", "black"],
}

def clean_text(text: str, preset: SymbolPreset) -> torch.LongTensor:
    """Convert raw text to tensor according to preset symbols."""
    cleaner_map = {
        1: japanese_tokenization_cleaners,
        2: japanese_cleaners,
        3: japanese_cleaners2,
        4: japanese_tokenization_cleaners,
    }
    cleaner = cleaner_map.get(preset.id, japanese_tokenization_cleaners)
    seq = transform.cleaned_text_to_sequence(cleaner(text), preset.symbols)
    return torch.LongTensor(commons.intersperse(seq, 0)) if commons else torch.LongTensor(seq)

class Window(QWidget):
    SAMPLE_RATE = 22050

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PJSK‑MultiGUI")
        QApplication.setFont(QFont("SimSun", 12))
        self.resize(1080, 720)
        self._center_on_screen()

        self.hps = None  # type: ignore
        self.model: Optional[SynthesizerTrn] = None
        self.current_preset = SYMBOL_PRESETS["default"]
        self.multi_speaker = False
        self.speaker_id: int = 0
        self.current_audio = None  # type: ignore
        self.current_audio_path: Optional[Path] = None
        """
        self.initUI()
        self.loadModel = False
        self.loadConfig = False
        self.multiSpeaker = False
        self.character = None
        self.speed = 1
        self.fileName = ''
        self.audio = None
        self.symbolType = 1
        self.MultiId = 0
        """

        self._init_ui()
    def _init_ui(self) -> None:
        layout = QGridLayout(self)

        # --- Model selection group
        model_group = QGroupBox("选择模型")
        mg_layout = QVBoxLayout()
        self.cfg_path_edit = QLineEdit()
        self.cfg_path_edit.setReadOnly(True)
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setReadOnly(True)

        cfg_btn = QPushButton("选择配置")
        cfg_btn.clicked.connect(self._select_config)
        model_btn = QPushButton("选择文件")
        model_btn.clicked.connect(self._select_model)

        row1 = QHBoxLayout(); row1.addWidget(cfg_btn); row1.addWidget(self.cfg_path_edit)
        row2 = QHBoxLayout(); row2.addWidget(model_btn); row2.addWidget(self.model_path_edit)
        mg_layout.addLayout(row1); mg_layout.addLayout(row2)
        model_group.setLayout(mg_layout)
        layout.addWidget(model_group, 0, 0)

        # --- Speaker selection
        self.spk_group = QGroupBox("当前角色")
        spk_layout = QVBoxLayout()
        self.spk_combo = QComboBox(); self.spk_combo.currentTextChanged.connect(self._speaker_changed)
        spk_btn = QPushButton("确定"); spk_btn.clicked.connect(self._confirm_speaker)
        self.spk_label = QLabel("当前选择：")
        spk_bottom = QHBoxLayout(); spk_bottom.addWidget(self.spk_label); spk_bottom.addStretch(); spk_bottom.addWidget(spk_btn)
        spk_layout.addWidget(self.spk_combo); spk_layout.addLayout(spk_bottom)
        self.spk_group.setLayout(spk_layout)
        layout.addWidget(self.spk_group, 1, 0)

        # --- TTS input
        tts_group = QGroupBox("语音合成")
        tts_layout = QVBoxLayout()
        tts_layout.addWidget(QLabel("输入日语原文"))
        self.text_edit = QTextEdit(); self.text_edit.setMaximumHeight(150)
        tts_layout.addWidget(self.text_edit)

        slider_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Orientation.Horizontal); self.speed_slider.setRange(50, 200); self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"当前语速：{v/100:.2f}"))
        self.speed_label = QLabel("当前语速：1.00")
        gen_btn = QPushButton("生成"); gen_btn.clicked.connect(self._generate_audio)
        slider_row.addWidget(self.speed_slider); slider_row.addWidget(self.speed_label); slider_row.addWidget(gen_btn)
        tts_layout.addLayout(slider_row)
        tts_group.setLayout(tts_layout)
        layout.addWidget(tts_group, 2, 0, 2, 1)

        # --- Output section
        out_group = QGroupBox("输出")
        out_layout = QHBoxLayout()
        play_btn = QPushButton("播放"); play_btn.clicked.connect(self._play_audio)
        save_btn = QPushButton("保存"); save_btn.clicked.connect(self._save_audio)
        out_layout.addWidget(play_btn); out_layout.addWidget(save_btn)
        out_group.setLayout(out_layout)
        layout.addWidget(out_group, 4, 0)

        # --- Log / info panel
        self.log_view = QTextEdit(); self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 0, 1, 5, 1)

    def _select_config(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择配置", "./", "Config (*.json)")
        if not file_path:
            return
        self.cfg_path_edit.setText(file_path)
        self._load_config(Path(file_path))

    def _select_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择模型", "./", "Model (*.pth)")
        if not file_path:
            return
        self.model_path_edit.setText(file_path)
        self._load_model(Path(file_path))

    def _load_config(self, cfg_path: Path) -> None:
        try:
            self.hps = utils.get_hparams_from_file(str(cfg_path))
            self._update_symbol_preset(cfg_path.name)
            self._populate_speaker_combo(cfg_path.name)
            self._log(f"配置文件加载成功: {cfg_path.name}")
        except Exception as exc:
            self._error(f"配置文件加载失败: {exc}")

    def _load_model(self, model_path: Path) -> None:
        if self.hps is None:
            self._error("请先载入配置文件。")
            return
        try:
            self.model = SynthesizerTrn(
                len(self.current_preset.symbols),
                self.hps.data.filter_length // 2 + 1,
                self.hps.train.segment_size // self.hps.data.hop_length,
                n_speakers=self.hps.data.n_speakers,
                **self.hps.model,
            )
            self.model.eval()
            utils.load_checkpoint(str(model_path), self.model, None)
            self._log(f"模型文件加载成功: {model_path.name}")
        except Exception as exc:
            self._error(f"模型文件加载失败: {exc}")

    def _update_symbol_preset(self, cfg_name: str) -> None:
        preset_key = CONFIG_TO_PRESET.get(cfg_name, "default")
        self.current_preset = SYMBOL_PRESETS[preset_key]
        self._log(f"使用符号预设: {preset_key}")

    def _populate_speaker_combo(self, cfg_name: str) -> None:
        self.spk_combo.clear()
        speakers = MULTI_SPK_GROUPS.get(cfg_name)
        if speakers:
            self.spk_combo.addItems(speakers)
            self.multi_speaker = True
            self.speaker_id = 0
        else:
            self.spk_combo.addItem(cfg_name.split(".")[0])
            self.multi_speaker = False
            self.speaker_id = 0
        # Trigger label update
        self._speaker_changed(self.spk_combo.currentText())

    def _speaker_changed(self, name: str) -> None:
        if self.multi_speaker:
            self.speaker_id = self.spk_combo.currentIndex()
        self.spk_label.setText(f"当前选择：{name}")

    def _confirm_speaker(self) -> None:
        self._log(self.spk_label.text())

    def _center_on_screen(self) -> None:
        geometry = self.frameGeometry(); geometry.moveCenter(self.screen().availableGeometry().center()); self.move(geometry.topLeft())
        
    def _play_audio(self):
        if not self.current_audio_path or not self.current_audio_path.exists():
            self._error("没有可播放的音频文件。请先生成音频。")
            return
        try:
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(str(self.current_audio_path)))
            effect.setLoopCount(1)
            effect.setVolume(1.0)
            effect.play()
            self._playing_effect = effect
            effect.play()
            self._log(f"播放: {self.current_audio_path.name}")
        except Exception as e:
            self._error(f"播放失败: {e}")

    def _generate_audio(self) -> None:
        if self.model is None or self.hps is None:
            self._error("模型或配置未加载。请先选择模型和配置文件。")
            return
        raw_text = self.text_edit.toPlainText().strip()
        if not raw_text:
            self._error("请输入要合成的文本。")
            return
        self._log("开始生成音频...")
        
        try:
            with torch.no_grad():
                raw_text = self.text_edit.toPlainText()
                raw_text = raw_text.replace('\n', ' ').strip()
                stn = clean_text(raw_text, self.current_preset)
                x_tst = stn.unsqueeze(0)
                x_len = torch.LongTensor([stn.size(0)])
                infer_kwargs = dict(
                    noise_scale=0.667,
                    noise_scale_w=0.8,
                    length_scale=self.speed_slider.value() / 100.0,
                )
                if self.multi_speaker:
                    audio = self.model.infer(x_tst, x_len, sid=torch.LongTensor([self.speaker_id]), **infer_kwargs)[0][0, 0].cpu().numpy()
                else:
                    audio = self.model.infer(x_tst, x_len, **infer_kwargs)[0][0, 0].cpu().numpy()
                # Save to temp file
                self.current_audio = audio
                temp_dir = Path(tempfile.gettempdir()) / "PJSK-MultiGUI"
                temp_dir.mkdir(exist_ok=True)
                safe_name = raw_text.replace("?", "").strip()[:10] or "voice"
                self.current_audio_path = temp_dir / f"{safe_name}_{random.randint(1000,9999)}.wav"
                sf.write(self.current_audio_path, audio, self.SAMPLE_RATE)
                self._log("音频生成成功。")
        except Exception as exc:
            self._error(f"推理失败: {exc}")
    
    def _save_audio(self) -> None:
        if self.current_audio is None:
            self._error("没有生成音频可保存。请先生成音频。")
            return
        target, _ = QFileDialog.getSaveFileName(self, "Save WAV", "result.wav", "WAV (*.wav)")
        if not target:
            return
        try:
            sf.write(target, self.current_audio, self.SAMPLE_RATE)
            self._log(f"保存到: {target}")
        except Exception as exc:
            self._error(f"保存失败: {exc}")

    def _log(self, message: str) -> None:
        logger.info(message)
        self.log_view.append(message)

    def _error(self, message: str) -> None:
        logger.error(message)
        self.log_view.append(f"Error: {message}")

def main() -> None:
    try:
        app = QApplication(sys.argv)
        ex = Window()
        ex.show()
        sys.exit(app.exec())
    except Exception as exc:
        logger.critical(f"Fatal error: {exc}")


if __name__ == '__main__':
    main()
