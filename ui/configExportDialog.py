# -*- coding: utf-8 -*-
#
# criado por: gerador de código pyqt5 ui v5.15.1
#
# aviso: qualquer mudança manual feita nesse arquivo poderá ser perdida quando o
# pyuic5 rodar novamente. não editar esse arquivo a não ser que saiba o que está fazendo


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_TemplateConfigDialog(object):
    def setupUi(self, TemplateConfigDialog):
        TemplateConfigDialog.setObjectName("TemplateConfigDialog")
        TemplateConfigDialog.resize(400, 300)
        self.buttonBox = QtWidgets.QDialogButtonBox(TemplateConfigDialog)
        self.buttonBox.setGeometry(QtCore.QRect(30, 240, 341, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Save)
        self.buttonBox.setObjectName("buttonBox")
        self.configJsonTextField = QtWidgets.QPlainTextEdit(TemplateConfigDialog)
        self.configJsonTextField.setGeometry(QtCore.QRect(10, 10, 381, 221))
        self.configJsonTextField.setObjectName("configJsonTextField")
        self.copyConfigButton = QtWidgets.QPushButton(TemplateConfigDialog)
        self.copyConfigButton.setGeometry(QtCore.QRect(10, 240, 95, 34))
        self.copyConfigButton.setObjectName("copyConfigButton")

        self.retranslateUi(TemplateConfigDialog)
        
        self.buttonBox.rejected.connect(TemplateConfigDialog.reject)
        self.buttonBox.accepted.connect(TemplateConfigDialog.accept)
        
        QtCore.QMetaObject.connectSlotsByName(TemplateConfigDialog)

    def retranslateUi(self, TemplateConfigDialog):
        _translate = QtCore.QCoreApplication.translate
        
        TemplateConfigDialog.setWindowTitle(_translate("TemplateConfigDialog", "diálogo"))
        self.copyConfigButton.setText(_translate("TemplateConfigDialog", "copiar"))