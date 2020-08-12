# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'admin_screen_ui.ui'
##
## Created by: Qt User Interface Compiler version 5.15.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
    QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
    QPixmap, QRadialGradient)
from PySide2.QtWidgets import *


class Ui_AdminScreen(object):
    def setupUi(self, AdminScreen):
        if not AdminScreen.objectName():
            AdminScreen.setObjectName(u"AdminScreen")
        AdminScreen.resize(790, 623)
        self.gridLayout = QGridLayout(AdminScreen)
        self.gridLayout.setObjectName(u"gridLayout")
        self.newAccountButton = QPushButton(AdminScreen)
        self.newAccountButton.setObjectName(u"newAccountButton")

        self.gridLayout.addWidget(self.newAccountButton, 0, 1, 1, 1)

        self.stopServerButton = QPushButton(AdminScreen)
        self.stopServerButton.setObjectName(u"stopServerButton")

        self.gridLayout.addWidget(self.stopServerButton, 0, 3, 1, 1)

        self.allAccountsButton = QPushButton(AdminScreen)
        self.allAccountsButton.setObjectName(u"allAccountsButton")

        self.gridLayout.addWidget(self.allAccountsButton, 0, 0, 1, 1)

        self.signoutButton = QPushButton(AdminScreen)
        self.signoutButton.setObjectName(u"signoutButton")

        self.gridLayout.addWidget(self.signoutButton, 0, 7, 1, 1)

        self.mdiArea = QMdiArea(AdminScreen)
        self.mdiArea.setObjectName(u"mdiArea")

        self.gridLayout.addWidget(self.mdiArea, 1, 0, 1, 8)

        self.startServerButton = QPushButton(AdminScreen)
        self.startServerButton.setObjectName(u"startServerButton")

        self.gridLayout.addWidget(self.startServerButton, 0, 2, 1, 1)

        self.serverAddressLineEdit = QLineEdit(AdminScreen)
        self.serverAddressLineEdit.setObjectName(u"serverAddressLineEdit")

        self.gridLayout.addWidget(self.serverAddressLineEdit, 0, 4, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 0, 6, 1, 1)

        self.serverStatusLabel = QLabel(AdminScreen)
        self.serverStatusLabel.setObjectName(u"serverStatusLabel")

        self.gridLayout.addWidget(self.serverStatusLabel, 0, 5, 1, 1)


        self.retranslateUi(AdminScreen)

        QMetaObject.connectSlotsByName(AdminScreen)
    # setupUi

    def retranslateUi(self, AdminScreen):
        AdminScreen.setWindowTitle(QCoreApplication.translate("AdminScreen", u"Form", None))
        self.newAccountButton.setText(QCoreApplication.translate("AdminScreen", u"New account", None))
        self.stopServerButton.setText(QCoreApplication.translate("AdminScreen", u"Stop server", None))
        self.allAccountsButton.setText(QCoreApplication.translate("AdminScreen", u"All accounts", None))
        self.signoutButton.setText(QCoreApplication.translate("AdminScreen", u"Sign Out", None))
        self.startServerButton.setText(QCoreApplication.translate("AdminScreen", u"Start server", None))
        self.serverAddressLineEdit.setInputMask(QCoreApplication.translate("AdminScreen", u"000.000.000.000:00000;-", None))
        self.serverAddressLineEdit.setText(QCoreApplication.translate("AdminScreen", u"127.0.0.1:12345", None))
        self.serverStatusLabel.setText(QCoreApplication.translate("AdminScreen", u"running", None))
    # retranslateUi

