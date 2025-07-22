import datetime
import os.path
import random
import sys
import time

import torch
from PyQt6.QtWidgets import QWidget, QMainWindow, QApplication, QVBoxLayout, QHBoxLayout, QToolTip, QComboBox, QSlider
from PyQt6.QtWidgets import QPushButton, QLabel, QSplitter, QFrame, QTextEdit, QGroupBox, QFileDialog, QGridLayout, \
    QLineEdit
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QUrl, QCoreApplication
from PyQt6.QtMultimedia import QSoundEffect,QAudioOutput,QMediaPlayer

from text import transform
from text.cleaners import japanese_tokenization_cleaners,japanese_cleaners2,japanese_cleaners
from models import SynthesizerTrn
import commons
import utils
import soundfile as sf
import janome
import logging

logger = logging.getLogger('test_logger')
# 设置日志等级
logger.setLevel(logging.DEBUG)
# 追加写入文件a ，设置utf-8编码防止中文写入乱码
test_log = logging.FileHandler('./logs/info.log', 'a', encoding='utf-8')
test_log.setLevel(logging.DEBUG)
# 向文件输出的日志信息格式
formatter = logging.Formatter(
    '%(asctime)s - %(filename)s - line:%(lineno)d - %(levelname)s - %(message)s -%(process)s')
test_log.setFormatter(formatter)
# 加载文件到logger对象中
logger.addHandler(test_log)


symbolDict = {
    'airi': 1,
    'mizuki':1,
    'saki': 1,
    'ichika':2,
    'ena': 3,
    'mmj': 3,
    'mafuyu': 3,
    'kanade': 4,
    'honami': 3,
    'shiho':3,
    'mafuyu_real':3,
    'vbs': 3,
    'ws':3
}

symbols = list(' !"&*,-.?ABCINU[]abcdefghijklmnoprstuwyz{}~')
hps = None
net_g = None

def change_symbols(type):
    global symbols
    if type == 1:
        symbols = list(' !"&*,-.?ABCINU[]abcdefghijklmnoprstuwyz{}~')
    elif type == 2:
        _pad        = '_'
        _punctuation = ',.!?-'
        _letters = 'AEINOQUabdefghijkmnoprstuvwyzʃʧ↓↑ '
        symbols = [_pad] + list(_punctuation) + list(_letters)
    elif type == 3:
        _pad = '_'
        _punctuation = ',.!?-~…'
        _letters = 'AEINOQUabdefghijkmnoprstuvwyzʃʧʦ↓↑ '
        symbols = [_pad] + list(_punctuation) + list(_letters)
    elif type == 4:
        _pad = '_'
        _punctuation = ';:,.!?¡¿—…"«»“” '
        _letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        _letters_ipa = "ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲʷˠˤ˞↓↑→↗↘'̩'ᵻ"
        symbols = [_pad] + list(_punctuation) + list(_letters) + list(_letters_ipa)

def get_text_type1(text, hps):
    text_norm = transform.cleaned_text_to_sequence(text,symbols)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = torch.LongTensor(text_norm)
    return text_norm

def get_text_type2(text, hps):
    text_norm = transform.cleaned_text_to_sequence(text,symbols)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = torch.LongTensor(text_norm)
    return text_norm

def get_text_type3(text, hps):
    text_norm = transform.cleaned_text_to_sequence(text,symbols)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = torch.LongTensor(text_norm)
    return text_norm

def load_checkpoint(path):
    print(555)
    try:
        utils.load_checkpoint(path, net_g, None)
    except Exception as e:
        print(e)
        logger.error(e)
    print(987)

class Window(QWidget):

    def __init__(self):
        super(Window, self).__init__()
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
    def initUI(self):
        QApplication.setFont(QFont('宋体', 12))
        self.resize(1080, 720)
        self.center()

        grid = QGridLayout()
        grid.spacing()
        # group1
        group_box1_choose_config2 = QPushButton("选择配置")
        group_box1_choose_config2.clicked.connect(self.openFileConfig)
        self.group_box1_line2 = QLineEdit()
        group_box1_hbox2 = QHBoxLayout()
        group_box1_hbox2.addWidget(group_box1_choose_config2)
        group_box1_hbox2.addWidget(self.group_box1_line2)

        group_box1_choose_model = QPushButton("选择文件")
        group_box1_choose_model.clicked.connect(self.openFileModel)
        self.group_box1_line = QLineEdit()
        group_box1_hbox = QHBoxLayout()
        group_box1_hbox.addWidget(group_box1_choose_model)
        group_box1_hbox.addWidget(self.group_box1_line)



        group_box1_vbox = QVBoxLayout()
        group_box1_vbox.addLayout(group_box1_hbox2)
        group_box1_vbox.addLayout(group_box1_hbox)

        group_box1 = QGroupBox("选择模型")
        group_box1.setLayout(group_box1_vbox)
        grid.addWidget(group_box1, 0, 0, 1, 1)

        # group2
        group_box2 = QGroupBox("当前角色")
        self.group_box2_v1 = QVBoxLayout()
        self.groupCombo = QComboBox()
        self.group_box2_h1 = QHBoxLayout()

        self.groupCombo.textActivated[str].connect(self.comboChange)
        self.combo_label = QLabel("当前选择：")

        self.group_box2_btn = QPushButton("确定")
        self.group_box2_btn.clicked.connect(self.chooseCharacter)
        self.group_box2_h1.addWidget(self.combo_label)
        self.group_box2_h1.addStretch(1)
        self.group_box2_h1.addWidget(self.group_box2_btn)

        self.group_box2_v1.addWidget(self.groupCombo)
        self.group_box2_v1.addLayout(self.group_box2_h1)

        group_box2.setLayout(self.group_box2_v1)
        grid.addWidget(group_box2, 1, 0, 1, 1)

        # group3
        group_box3 = QGroupBox("语音合成")
        group_box3_v1 = QVBoxLayout()
        self.group_box3_textarea = QTextEdit()
        self.group_box3_textarea.adjustSize()
        self.group_box3_textarea.setMaximumHeight(150)

        group_box3_label = QLabel("输入日语原文")
        group_box3_h1 = QHBoxLayout()

        sld = QSlider(Qt.Orientation.Horizontal, self)
        sld.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # sld.setGeometry(30, 40, 200, 30)
        sld.setValue(100)
        sld.valueChanged[int].connect(self.changeValue)
        sld.setMinimum(0)
        sld.setMaximum(200)
        self.sld_label = QLabel("当前语速：1")
        group_box3_btn = QPushButton("生成")
        group_box3_btn.clicked.connect(self.createVoice)
        group_box3_h1.addWidget(sld)
        group_box3_h1.addWidget(self.sld_label)
        group_box3_h1.addWidget(group_box3_btn)

        group_box3_v1.addWidget(group_box3_label)
        group_box3_v1.addSpacing(2)
        group_box3_v1.addWidget(self.group_box3_textarea)
        group_box3_v1.addLayout(group_box3_h1)
        group_box3.setLayout(group_box3_v1)
        grid.addWidget(group_box3, 2, 0, 2, 1)

        vbox = QVBoxLayout()
        grid.addLayout(vbox.addStretch(1), 3, 0, 2, 1)
        # group4
        group_box4 = QGroupBox("输出")
        group_box4_h1 = QHBoxLayout()
        group_box4_btn = QPushButton("播放")
        group_box4_save = QPushButton("保存")
        group_box4_save.clicked.connect(self.saveWav)
        group_box4_btn.clicked.connect(self.playSound)
        group_box4_h1.addWidget(group_box4_btn)
        # group_box4_h1.addStretch(1)
        group_box4_h1.addWidget(group_box4_save)
        group_box4.setLayout(group_box4_h1)
        grid.addWidget(group_box4, 4, 0, 1, 1)

        # right
        self.text_area = QTextEdit()
        self.text_area.adjustSize()
        grid.addWidget(self.text_area, 0, 1, 5, 1)
        self.text_area.setReadOnly(True)
        self.text_area.sizeHint()

        self.setLayout(grid)

        # self.setGeometry(100, 100, 1080, 720)
        self.setWindowTitle('PJSK-MultiGUI')
        self.show()



    def openFileModel(self):
        try:
            modelName, modelType = QFileDialog.getOpenFileName(self, "选择模型", "./", "Pth file (*.pth)")
            print(modelName)
            if modelName == '':
                self.textUpdate('Error: ' + '模型未加载')
                return 0
            self.group_box1_line.setText(modelName)
            self.group_box1_line.setReadOnly(True)
            print('load')
            load_checkpoint(modelName)
        except Exception as e:
            self.textUpdate('Error: ' + str(e))
            logger.error(e)
            return 0
        self.textUpdate(modelName + " 模型加载完成")
        self.loadModel = True



    def openFileConfig(self):
        try:
            modelName, modelType = QFileDialog.getOpenFileName(self, "选择模型", "./", "Config file (*.json)")

            if modelName.split('/')[-1] == 'mmj.json':
                self.groupCombo.clear()
                self.groupCombo.addItem('minori')
                self.groupCombo.addItem('haruka')
                self.groupCombo.addItem('airi')
                self.groupCombo.addItem('shizuku')
                self.combo_label.setText('当前选择：minori')
                self.character = 'minori'
                self.MultiId = 0
                self.multiSpeaker = True
            elif modelName.split('/')[-1] == 'vbs.json':
                self.groupCombo.clear()
                self.groupCombo.addItem('akito')
                self.groupCombo.addItem('an')
                self.groupCombo.addItem('kohane')
                self.groupCombo.addItem('toya')
                self.combo_label.setText('当前选择：akito')
                self.character = 'minori'
                self.MultiId = 0
                self.multiSpeaker = True
            elif modelName.split('/')[-1] == 'ws.json':
                self.groupCombo.clear()
                self.groupCombo.addItem('emu')
                self.groupCombo.addItem('nene')
                self.groupCombo.addItem('rui')
                self.groupCombo.addItem('tsukasa')
                self.combo_label.setText('当前选择：emu')
                self.character = 'minori'
                self.MultiId = 0
                self.multiSpeaker = True
            elif modelName.split('/')[-1] == 'mafuyu.json':
                self.groupCombo.clear()
                self.groupCombo.addItem('white')
                self.groupCombo.addItem('black')
                self.combo_label.setText('当前选择：white')
                self.character = 'white'
                self.MultiId = 0
                self.multiSpeaker = True
            else:
                self.groupCombo.clear()
                self.groupCombo.addItem(modelName.split('/')[-1].split('.')[0])
                self.character = modelName.split('/')[-1].split('.')[0]
                text = "当前选择：" + modelName.split('/')[-1].split('.')[0]
                print(5556)
                self.combo_label.setText(text)
                print(55)
                self.combo_label.adjustSize()
                self.multiSpeaker = False
                print(66)
            self.symbolType = symbolDict[modelName.split('/')[-1].split('.')[0]]
            print(self.symbolType)
            print(self.symbolType)
            change_symbols(self.symbolType)
        except Exception as e:
            print(e)
            logger.error(e)
            self.textUpdate('加载错误：未识别的文件 ' + str(e))

            # self.textUpdate('Error: ' + str(e))
            return 0
        # 加载hps配置
        try:
            global hps
            hps = utils.get_hparams_from_file(modelName)
            print(777)
            # 生成net_g
            global net_g
            net_g = SynthesizerTrn(
                len(symbols),
                hps.data.filter_length // 2 + 1,
                hps.train.segment_size // hps.data.hop_length,
                n_speakers=hps.data.n_speakers,
                **hps.model)
            net_g.eval()
        except Exception as e:
            self.textUpdate('hps 加载失败')
            logger.error(e)
            return 0
        # print(net_g)
        # 其它配置
        self.group_box1_line2.setText(modelName)
        self.group_box1_line2.setReadOnly(True)
        self.loadConfig = True
        self.textUpdate(modelName + " 配置文件加载完成")

    def center(self):

        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()

        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def chooseCharacter(self):
        self.textUpdate(self.combo_label.text())

    def comboChange(self, text):
        if text == 'minori' or text == 'akito' or text=='emu':
            self.MultiId = 0
        elif text == 'haruka' or text == 'an' or text =='nene':
            self.MultiId = 1
        elif text == 'airi' or text == 'kohane' or text =='rui':
            self.MultiId = 2
        elif text == 'shizuku' or text == 'toya' or text=='tsukasa':
            self.MultiId = 3
        elif text == 'white':
            self.MultiId = 0
        elif text == 'black':
            self.MultiId = 1
        text = "当前选择：" + text
        self.character = text
        self.combo_label.setText(text)
        self.combo_label.adjustSize()

    def changeValue(self, value):
        self.speed = value / 100
        self.sld_label.setText("当前语速：" + str((value / 100)))

    def playSound(self):
        # print(self.audio)
        print('播放' + self.fileName)
        file = self.fileName  # 音频文件路径
        effect = QSoundEffect(QCoreApplication.instance())
        effect.setSource(QUrl.fromLocalFile(file))
        print(QUrl.fromLocalFile(file))
        # effect.setSource(QUrl.fromLocalFile(self.audio))
        effect.setLoopCount(1)
        effect.setVolume(1)
        effect.play()
        # player = QMediaPlayer()
        # content =
        # audio_output = QAudioOutput()
        # player.setAudioOutput(audio_output)
        # player.setSource(self.audio)
        # audio_output.setVolume(1)

    def saveWav(self):
        if not os.path.exists('results'):
            os.makedirs('results')
        sf.write('results/' + self.fileName.split('/')[1], self.audio, 22050)
        self.textUpdate('保存到' + 'results/' + self.fileName.split('/')[1])

    def textUpdate(self, msg):
        origin_text = self.text_area.toPlainText()
        self.text_area.append(msg)

    def createVoice(self):
        if not self.loadModel:
            self.textUpdate('没有载入模型!')
        elif not self.loadConfig:
            self.textUpdate("没有载入配置")
        else:
            if self.fileName != '':
                if os.path.exists(self.fileName):
                    os.remove(os.path.join(self.fileName))
                    print(self.fileName)
                    print('delete')
            self.textUpdate("生成中...")
            print('this2')
            try:
                ret = self.jtts(self.group_box3_textarea.toPlainText(),self.speed)
            except:

                return 0
            if ret != 'Error':
                self.textUpdate("成功，" + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
            self.textUpdate("————————————————")

    def jtts(self,text, length_scale):
        print(text,length_scale)
        # tokenization
        # print(length_scale)
        # print(net_g)
        # print(net_g)
        # print(symbols)
        # print(hps)
        print(self.symbolType)
        try:
            if self.symbolType == 1:
                stn_tst = get_text_type1(japanese_tokenization_cleaners(text), hps)
            if self.symbolType == 2:
                stn_tst = get_text_type2(japanese_cleaners(text), hps)
            elif self.symbolType == 3:
                stn_tst = get_text_type3(japanese_cleaners2(text), hps)
            elif self.symbolType == 4:
                stn_tst = get_text_type1(japanese_tokenization_cleaners(text), hps)
            if not os.path.exists('playSounds'):
                os.makedirs('playSounds')
        except Exception as e:
            logger.error(e)
            self.textUpdate(f'KeyError: {str(e)}')
        with torch.no_grad():
            print('this1')
            try:
                x_tst = stn_tst.unsqueeze(0)
                x_tst_lengths = torch.LongTensor([stn_tst.size(0)])

                print(self.character)
                if self.multiSpeaker:
                    print(1111)
                    sid = torch.LongTensor([self.MultiId])
                    print(sid)
                    audio = net_g.infer(x_tst, x_tst_lengths, sid=sid, noise_scale=.667, noise_scale_w=0.8, length_scale=length_scale)[0][
                        0, 0].data.float().numpy()
                else:

                    try:
                        audio = net_g.infer(x_tst, x_tst_lengths, noise_scale=.667, noise_scale_w=0.8, length_scale=length_scale)[0][
                            0, 0].data.float().numpy()
                    except Exception as e:
                        print(e)
                    print(333)
                filename = 'playSounds/' + text.replace('?', '') + str(random.randint(1,100))+'.wav'
                self.fileName = filename
                self.audio = audio
                print(self.fileName)
                sf.write(filename, audio, 22050)
            except Exception as e:
                self.textUpdate(f'Error: {str(e)}')
                logger.error(e)
                return 'Error'
def main():


    try:
        app = QApplication(sys.argv)
        ex = Window()
        sys.exit(app.exec())
    except Exception as e:
        logger.error(e)


if __name__ == '__main__':
    main()
