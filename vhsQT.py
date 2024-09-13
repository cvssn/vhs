import os
import sys
from pathlib import Path

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QLibraryInfo
from PyQt5.QtCore import QFile, QTextStream
import darkdetect

from app import VhsApp
from app import logger


os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(QLibraryInfo.PluginsPath)

def crash_handler(type, value, tb):
    logger.trace(value)
    logger.exception("exceção não detectada: {0}".format(str(value)))
    
    sys.exit(1)

# instalar o manipulador de exceções
sys.excepthook = crash_handler

def main():
    translator = QtCore.QTranslator()
    locale = QtCore.QLocale.system().name()

    print("vhs")

    # se executado pelo executável pyinstaller, o attr congelado será verdadeiro
    if getattr(sys, 'frozen', False):
        # _meipass contém o diretório temporário do pyinstaller
        base_dir = Path(sys._MEIPASS)
        locale_file = str((base_dir / 'translate' / f'{locale}.qm').resolve())
    else:
        base_dir = Path(__file__).absolute().parent
        locale_file = str((base_dir / 'translate' / f'{locale}.qm').resolve())

    print(f"tente carregar o locale {locale}: {locale_file}")
    
    if translator.load(locale_file):
        print(f'localização carregada: {locale}') # nome, diretório
    else:
        print("usando tradução padrão")

    app = QtWidgets.QApplication(sys.argv)
    app.installTranslator(translator)

    if darkdetect.isDark():
        import ui.breeze_resources
        
        darkthm = QFile(":/dark/stylesheet.qss")
        darkthm.open(QFile.ReadOnly | QFile.Text)
        darkthm_stream = QTextStream(darkthm)
        
        app.setStyleSheet(darkthm_stream.readAll())

    window = VhsApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()