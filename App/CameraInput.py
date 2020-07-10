from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *
from PyQt5.QtMultimedia import *
from PyQt5.QtMultimediaWidgets import *

import os
import sys
import time

import cv2
import numpy as np



class CameraInput(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(CameraInput, self).__init__(*args, **kwargs)

        self.available_cameras = QCameraInfo.availableCameras()
        if not self.available_cameras:
            pass #quit

        self.lastImage = None
        self.lastID = None

        self.status = QStatusBar()
        self.setStatusBar(self.status)


        self.save_path = ""

        self.viewfinder = QCameraViewfinder()
        self.viewfinder.show()
        self.setCentralWidget(self.viewfinder)

        # Set the default camera.
        self.select_camera(0)

        # Setup tools
        camera_toolbar = QToolBar("Camera")
        camera_toolbar.setIconSize(QSize(14, 14))
        self.addToolBar(camera_toolbar)

        if True:
            photo_action = QAction(QIcon(os.path.join('Data', 'camera-black.png')), "Take photo...", self)
            photo_action.setStatusTip("Take photo of current view")
            photo_action.triggered.connect(self.clickTestCapture)
            camera_toolbar.addAction(photo_action)

        camera_selector = QComboBox()
        camera_selector.addItems([c.description() for c in self.available_cameras])
        camera_selector.currentIndexChanged.connect( self.select_camera )

        camera_toolbar.addWidget(camera_selector)
        
        self.capture.capture()


        self.setWindowTitle("Camera input viewer")
        self.show()

    def select_camera(self, i):
        self.camera = QCamera(self.available_cameras[i])
        self.camera.setViewfinder(self.viewfinder)
        self.camera.setCaptureMode(QCamera.CaptureStillImage)
        self.camera.error.connect(lambda: self.alert(self.camera.errorString()))
        self.camera.start()

        self.capture = QCameraImageCapture(self.camera)
        self.capture.setCaptureDestination(QCameraImageCapture.CaptureToBuffer)

        self.capture.error.connect(lambda i, e, s: self.alert(s))
        self.capture.imageCaptured.connect(self.storeLastFrame)

        self.current_camera_name = self.available_cameras[i].description()
        self.save_seq = 0

    def getLastFrame(self):
        imageID = self.capture.capture()
        return self.qImageToMat(self.lastImage)
    
    def storeLastFrame(self, idImg:int, preview:QImage):
        self.lastImage = preview
        self.lastID = idImg
    
    def clickTestCapture(self):
        frame = self.getLastFrame()
        print('\nLast frame: ' + str(frame))
        cv2.imshow('Test capture',frame)
        cv2.waitKey(0)

    def qImageToMat(self,incomingImage):
        url = '.\\Data\\temp.png'
        incomingImage.save(url, 'png')
        mat = cv2.imread(url)
        return mat



if __name__ == '__main__':

    app = QApplication(sys.argv)
    app.setApplicationName("NSA_Viewer")

    window = CameraInput()
    app.exec_()