from Util import printHeadLine, resizeCvFrame
import queue
import time
import cv2
import sys
import os
from Util import SwitchButton
import pyqtgraph as pg
import numpy as np

from PyQt5 import QtWidgets as Qtw
from PyQt5.QtCore import Qt, QThread,  pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap

# Path to OpenPose installation folder on your system.
openposePATH = r'C:\OpenPose'

sys.path.append(openposePATH + r'\build\python\openpose\Release')
releasePATH = r'C:\OpenPose\build\x64\Release'
binPATH = openposePATH + r'\build\bin'
modelsPATH = openposePATH + r'\models'
os.environ['PATH'] = os.environ['PATH'] + ';' + releasePATH + ';' + binPATH + ';'
import pyopenpose as op


## bufferless VideoCapture
# No longer used
class VideoCaptureThread(QThread):
    newPixmap = pyqtSignal(QImage)
    def __init__(self, nameSource=0):
        super().__init__()
        self.running = True
        print('Connection to ' + str(nameSource))
        try:
            self.cap = cv2.VideoCapture(nameSource)
        except:
            print('Connection to video stream failed.')
            self.running = False

        self.q = queue.Queue()
        self.emissionFPS = 12.0
        self.lastTime = time.time()
        printHeadLine('Video stream ready',False)

    # read frames as soon as they are available, keeping only most recent one
    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break
            if not self.q.empty():
                try:
                    self.q.get_nowait()   # discard previous (unprocessed) frame
                except Queue.Empty:
                    pass
            self.q.put(frame)
            
            if time.time() - self.lastTime > 1.0/self.emissionFPS:
                self.lastTime = time.time()
                rgbImage = cv2.cvtColor(self.q.get(), cv2.COLOR_BGR2RGB)
                h, w, ch = rgbImage.shape
                bytesPerLine = ch * w
                convertToQtFormat = QImage(rgbImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
                p = convertToQtFormat.scaled(640, 480, Qt.KeepAspectRatio)
                self.newPixmap.emit(p)

    def getLastFrame(self):
        return self.q.get()
    
    def release(self):
        self.cap.release()


class VideoAnalysisThread(QThread):
    newPixmap = pyqtSignal(QImage)
    def __init__(self, videoSource):
        super().__init__()
        self.running = False
        self.videoSource = videoSource
        params = dict()
        params["model_folder"] = modelsPATH
        params["face"] = False
        params["hand"] = True
        params["disable_multi_thread"] = False
        params["net_resolution"] = "-1x"+str(16*22) #Default 22

        ## Starting OpenPose ##
        #######################
        self.opWrapper = op.WrapperPython()
        self.opWrapper.configure(params)
        self.opWrapper.start()

        self.datum = op.Datum()
        self.lastTime = time.time()
        self.emissionFPS = 3.0
        self.fixedFps = True

        self.videoWidth = 1280 
        self.videoHeight = 720
    
    def run(self):
        while True:
            if self.running:
                if (time.time() - self.lastTime > 1.0/self.emissionFPS) or not self.fixedFps:
                    self.lastTime = time.time()

                    frame = self.videoSource.getLastFrame()
                    if type(frame) != type(None): #Check if frame exist, frame!=None is ambigious when frame is an array
                        frame = resizeCvFrame(frame, 0.5)
                        self.datum.cvInputData = frame
                        self.opWrapper.emplaceAndPop([self.datum])
                        frameOutput = self.datum.cvOutputData

                        rgbImage = cv2.cvtColor(frameOutput, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgbImage.shape
                        bytesPerLine = ch * w
                        convertToQtFormat = QImage(rgbImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
                        p = convertToQtFormat.scaled(self.videoWidth, self.videoHeight, Qt.KeepAspectRatio)
                        self.newPixmap.emit(p)
    
    @pyqtSlot(bool)
    def setState(self, s:bool):
        self.running = s
    
    def setResolutionStream(self, width:int, height:int):
        self.videoHeight = height
        self.videoWidth = width
    
    def setEmissionSpeed(self, fixedFPS:bool, fps:int):
        self.fixedFps=fixedFPS
        if self.fixedFps:
            self.emissionFPS = fps


class VideoViewer(Qtw.QGroupBox):
    def __init__(self):
        super().__init__('Camera feed')

        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.rawCamFeed = Qtw.QLabel(self)
        #self.label.setScaledContents(True)
        #self.rawCamFeed.setFixedSize(854,480)
        self.layout.addWidget(self.rawCamFeed,0,0,1,1)

        self.infoLabel = Qtw.QLabel('No info')
        self.layout.addWidget(self.infoLabel,1,0,1,1)

        self.pepperCamFeed = Qtw.QLabel(self)
        self.layout.addWidget(self.pepperCamFeed,0,1,1,1)

        self.autoAdjustable = False

    @pyqtSlot(QImage)
    def setImage(self, image):
        self.currentPixmap = QPixmap.fromImage(image)
        self.rawCamFeed.setPixmap(self.currentPixmap.scaled(self.rawCamFeed.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    @pyqtSlot(QImage)
    def setPepperImage(self, image):
        self.currentPixmapPepper = QPixmap.fromImage(image)
        self.pepperCamFeed.setPixmap(self.currentPixmapPepper.scaled(self.pepperCamFeed.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def resizeEvent(self, event):
        if self.autoAdjustable:
            try:
                w = self.rawCamFeed.width()
                h = self.rawCamFeed.height()
                self.rawCamFeed.setPixmap(self.currentPixmap.scaled(w,h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.rawCamFeed.setMinimumSize(100,100)

                w = self.pepperCamFeed.width()
                h = self.pepperCamFeed.height()
                self.pepperCamFeed.setPixmap(self.pepperCamFeed.scaled(w,h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.pepperCamFeed.setMinimumSize(100,100)
            except:
                pass
    
    def setVideoSize(self, width:int, height:int):
        self.rawCamFeed.setFixedSize(width,height)
    
    def setInfoText(self, info:str):
        if info:
            self.infoLabel.setText(info)
        else:
            self.infoLabel.setText('')
    

class TrainingWidget(Qtw.QWidget):
    def __init__(self, parent = None):
        super(TrainingWidget, self).__init__(parent)

        self.layout=Qtw.QGridLayout(self)
        self.layout.setColumnStretch(1,2)
        self.setLayout(self.layout)
        self.parent = parent

        self.simButton = SwitchButton(self)
        self.layout.addWidget(self.simButton,1,0,1,1)

        self.VideoViewer = VideoViewer()
        self.layout.addWidget(self.VideoViewer,0,0,1,1)

        self.cameraInput = CameraInput()

        videoHeight = 480 # 480p
        self.AnalysisThread = VideoAnalysisThread(self.cameraInput)
        self.AnalysisThread.newPixmap.connect(self.VideoViewer.setImage)
        self.AnalysisThread.newPixmap.connect(self.analyseNewImage)
        self.AnalysisThread.setResolutionStream(int(videoHeight * (16.0/9.0)), videoHeight)
        self.VideoViewer.setVideoSize(int(videoHeight * (16.0/9.0)), videoHeight)

        self.AnalysisThread.start()
        self.AnalysisThread.setState(True)
        self.simButton.clickedChecked.connect(self.AnalysisThread.setState)
        self.simButton.setChecked(True)

        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setBackground('w')
        self.graphWidget.setXRange(-0.5, 0.5)
        self.graphWidget.setYRange(-0.5, 0.5)
        #self.graphWidget.setMinimumSize(videoHeight,videoHeight)
        self.graphWidget.setAspectLocked(True)
        self.layout.addWidget(self.graphWidget, 0,1,2,1)
    
    def analyseNewImage(self, image):
        self.graphWidget.clear()
        rightHandKeys = self.handDataFormatting(1)
        if type(rightHandKeys) != type(None):
            #print(rightHandKeys)
            self.drawHand(rightHandKeys)

    def handDataFormatting(self, handID:int):
        ''' handID (int): 0->Left / 1->Right '''
        personID = 0
        outputArray = None

        handKeypoints = np.array(self.AnalysisThread.datum.handKeypoints)
        nbrPersonDetected = handKeypoints.shape[1] if handKeypoints.ndim >2 else 0

        infoText = ''
        infoText += str(nbrPersonDetected) + (' person detected' if nbrPersonDetected<2 else  ' person detected')

        if nbrPersonDetected > 0:
            handDetected = (handKeypoints[handID, personID].T[2].sum() > 1.0)
            if handDetected:
                infoText += ', ' + ('Right' if handID==1 else 'Left') + ' hand of person ' + str(personID+1) + ' detected.'
                normMax = (self.AnalysisThread.datum.handRectangles[personID][handID]).height

                handCenterX = handKeypoints[handID, personID].T[0].sum() / handKeypoints.shape[2]
                handCenterY = handKeypoints[handID, personID].T[1].sum() / handKeypoints.shape[2]
                outputArray = np.array([(handKeypoints[handID, personID].T[0] - handCenterX)/normMax,
                                        -(handKeypoints[handID, personID].T[1] - handCenterY)/normMax,
                                        (handKeypoints[handID, personID].T[2])])
        self.VideoViewer.setInfoText(infoText)
        return outputArray
    
    def drawHand(self, handKeypoints:np.ndarray):
        finger1 = handKeypoints[:, 0:5]
        finger2 = np.insert(handKeypoints[:, 5:9].T, 0, handKeypoints[:,0], axis=0).T
        finger3 = np.insert(handKeypoints[:, 9:13].T, 0, handKeypoints[:,0], axis=0).T
        finger4 = np.insert(handKeypoints[:, 13:17].T, 0, handKeypoints[:,0], axis=0).T
        finger5 = np.insert(handKeypoints[:, 17:21].T, 0, handKeypoints[:,0], axis=0).T

        self.graphWidget.plot(finger1[0], finger1[1], symbol='o', symbolSize=7, symbolBrush=('r'))
        self.graphWidget.plot(finger2[0], finger2[1], symbol='o', symbolSize=7, symbolBrush=('y'))
        self.graphWidget.plot(finger3[0], finger3[1], symbol='o', symbolSize=7, symbolBrush=('g'))
        self.graphWidget.plot(finger4[0], finger4[1], symbol='o', symbolSize=7, symbolBrush=('b'))
        self.graphWidget.plot(finger5[0], finger5[1], symbol='o', symbolSize=7, symbolBrush=('m'))
        #self.graphWidget.plot(handKeypoints[0], handKeypoints[1], symbol='o', symbolSize=5, symbolBrush=('k'))
    

if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    from CameraInput import CameraInput
    import sys

    app = Qtw.QApplication(sys.argv)
    
    trainingWidget = TrainingWidget()
    trainingWidget.show()

    


    sys.exit(app.exec_())