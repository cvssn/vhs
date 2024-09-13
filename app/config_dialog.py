from PyQt5.QtWidgets import QDialog
from PyQt5 import QtWidgets, QtCore, QtGui

from ui import configExportDialog


class ConfigDialog(QDialog, configExportDialog.Ui_TemplateConfigDialog):
    def __init__(self, parent=None):
        super(ConfigDialog, self).__init__(parent)
        
        self.setupUi(self)
        
        print("conectar botões") # fornece o output esperado
        
        # self.connect(self.pushButton_Ok, SIGNAL("clicked()"), self.clickedOk)
        # self.connect(self.pushButton_Cancel, SIGNAL("clicked()"), self.clickedCancel)

        # como alternativa, tentei o seguinte sem melhorias:
        # self.pushButton_Ok.clicked.connect(self.clickedOk)
        # QObject.connect(self.pushButton_Cancel, SIGNAL("clicked()"), self.clickedCancel)

        # self.buttonBox.accepted.connect(self.clickedOk)
        self.copyConfigButton.clicked.connect(self.clickedCopy)
        
    @QtCore.pyqtSlot()
    def clickedCopy(self):
        self.configJsonTextField.selectAll()
        self.configJsonTextField.copy()
        
    @QtCore.pyqtSlot()
    def clickedOk(self):
        print("ok")