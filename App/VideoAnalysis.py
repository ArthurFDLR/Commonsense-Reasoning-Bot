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
        self.infoText = ''
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
    
    def getHandData(self, handID:int):
        ''' Return the key points of the hand seen in the image (cf. videoSource).
        
        Args:
            handID (int): 0 -> Left hand | 1 -> Right hand
        
        returns:
            np.ndarray((3,21),float): Coordinates x, y and the accuracy score for each 21 key points.
                                      None if the given hand is not detected.
        '''
        personID = 0
        outputArray = None

        handKeypoints = np.array(self.datum.handKeypoints)
        nbrPersonDetected = handKeypoints.shape[1] if handKeypoints.ndim >2 else 0

        self.infoText = ''
        self.infoText += str(nbrPersonDetected) + (' person detected' if nbrPersonDetected<2 else  ' person detected')

        if nbrPersonDetected > 0:
            handDetected = (handKeypoints[handID, personID].T[2].sum() > 1.0)
            if handDetected:
                handKeypoints = handKeypoints[handID, personID]
                self.infoText += ', ' + ('Right' if handID==1 else 'Left') + ' hand of person ' + str(personID+1) + ' detected.'

                lengthFingers = [np.sqrt((handKeypoints[0,0] - handKeypoints[i,0])**2 + (handKeypoints[0,1] - handKeypoints[i,1])**2) for i in [1,5,9,13,17]] #Initialize with the length of the first segment of each fingers
                for i in range(3): #Add length of other segments of each fingers
                    for j in range(len(lengthFingers)):
                        lengthFingers[j] += np.sqrt((handKeypoints[1+j*4+i+1, 0] - handKeypoints[1+j*4+i, 0])**2 + (handKeypoints[1+j*4+i+1, 1] - handKeypoints[1+j*4+i, 1])**2)
                normMax = max(lengthFingers)

                handCenterX = handKeypoints.T[0].sum() / handKeypoints.shape[0]
                handCenterY = handKeypoints.T[1].sum() / handKeypoints.shape[0]
                outputArray = np.array([(handKeypoints.T[0] - handCenterX)/normMax,
                                        -(handKeypoints.T[1] - handCenterY)/normMax,
                                        (handKeypoints.T[2])])
        return outputArray
    
    def getInfoText(self) -> str:
        return self.infoText
    
    def getFingerLength(self, fingerData):
        length = .0
        for i in range(fingerData.shape[0]-1):
            length += np.sqrt((fingerData[i+1,0] - fingerData[i,0])**2 + (fingerData[i+1,1] - fingerData[i,1])**2)
        return length


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
        self.graphWidget.setXRange(-1.0, 1.0)
        self.graphWidget.setYRange(-1.0, 1.0)
        #self.graphWidget.setMinimumSize(videoHeight,videoHeight)
        self.graphWidget.setAspectLocked(True)
        self.layout.addWidget(self.graphWidget, 0,1,2,1)
    
    def analyseNewImage(self, image):
        rightHandKeys = self.AnalysisThread.getHandData(1)
        self.graphWidget.clear()
        self.VideoViewer.setInfoText(self.AnalysisThread.getInfoText())
        if type(rightHandKeys) != type(None):
            self.drawHand(rightHandKeys)
    
    def drawHand(self, handKeypoints:np.ndarray):
        colors = ['r','y','g','b','m']
        data = [handKeypoints[:, 0:5],
                np.insert(handKeypoints[:, 5:9].T, 0, handKeypoints[:,0], axis=0).T,
                np.insert(handKeypoints[:, 9:13].T, 0, handKeypoints[:,0], axis=0).T,
                np.insert(handKeypoints[:, 13:17].T, 0, handKeypoints[:,0], axis=0).T,
                np.insert(handKeypoints[:, 17:21].T, 0, handKeypoints[:,0], axis=0).T]
        for i in range(len(data)):
            self.graphWidget.plot(data[i][0], data[i][1], symbol='o', symbolSize=7, symbolBrush=(colors[i]))
    
    

if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    from CameraInput import CameraInput
    import sys

    app = Qtw.QApplication(sys.argv)
    
    trainingWidget = TrainingWidget()
    trainingWidget.show()

    


    sys.exit(app.exec_())