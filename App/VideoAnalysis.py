from Util import printHeadLine, resizeCvFrame
import queue
import time
import cv2
import sys
import os

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

# bufferless VideoCapture
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
    
    def run(self):
        while True:
            if self.running:
                if time.time() - self.lastTime > 1.0/self.emissionFPS:
                    self.lastTime = time.time()

                    frame = self.videoSource.getLastFrame()
                    frame = resizeCvFrame(frame, 0.5)
                    self.datum.cvInputData = frame
                    self.opWrapper.emplaceAndPop([self.datum])
                    frameOutput = self.datum.cvOutputData

                    rgbImage = cv2.cvtColor(frameOutput, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgbImage.shape
                    bytesPerLine = ch * w
                    convertToQtFormat = QImage(rgbImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
                    p = convertToQtFormat.scaled(640, 480, Qt.KeepAspectRatio)
                    self.newPixmap.emit(p)
    
    @pyqtSlot(bool)
    def setState(self, s:bool):
        self.running = s

class VideoViewer(Qtw.QGroupBox):
    def __init__(self):
        super().__init__('Camera feed')

        self.layout=Qtw.QHBoxLayout(self)
        self.setLayout(self.layout)

        self.rawCamFeed = Qtw.QLabel(self)
        #self.label.setScaledContents(True)
        self.layout.addWidget(self.rawCamFeed)

        self.pepperCamFeed = Qtw.QLabel(self)
        self.layout.addWidget(self.pepperCamFeed)

    @pyqtSlot(QImage)
    def setImage(self, image):
        self.currentPixmap = QPixmap.fromImage(image)
        self.rawCamFeed.setPixmap(self.currentPixmap.scaled(self.rawCamFeed.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    @pyqtSlot(QImage)
    def setPepperImage(self, image):
        self.currentPixmapPepper = QPixmap.fromImage(image)
        self.pepperCamFeed.setPixmap(self.currentPixmapPepper.scaled(self.pepperCamFeed.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def resizeEvent(self, event):
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


if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    import sys

    showAnalysed = False

    app = Qtw.QApplication(sys.argv)

    appGui = VideoViewer()
    appGui.show()

    VideoThread = VideoCaptureThread('http://S9:S9@192.168.1.38:8080/video')
    VideoThread.start()

    AnalysisThread = VideoAnalysisThread(VideoThread)
    AnalysisThread.start()

    if showAnalysed:
        AnalysisThread.newPixmap.connect(appGui.setImage)
    else:
        VideoThread.newPixmap.connect(appGui.setImage)

    sys.exit(app.exec_())