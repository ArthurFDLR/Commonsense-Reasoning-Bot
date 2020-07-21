from Util import printHeadLine, resizeCvFrame
import queue
import time
from datetime import date
import cv2
import sys
import os
from Util import SwitchButton, ScrollLabel
import pyqtgraph as pg
import numpy as np
from CameraInput import CameraInput

from PyQt5 import QtWidgets as Qtw
from PyQt5.QtCore import Qt, QThread,  pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QDoubleValidator, QColor

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
        self.personID = 0
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
        self.personID = 0
        outputArray = None

        handKeypoints = np.array(self.datum.handKeypoints)
        nbrPersonDetected = handKeypoints.shape[1] if handKeypoints.ndim >2 else 0
        handAccuaracyScore = .0
        if nbrPersonDetected > 0:
            handAccuaracyScore = handKeypoints[handID, self.personID].T[2].sum()
            handDetected = (handAccuaracyScore > 1.0)
            if handDetected:
                handKeypoints = handKeypoints[handID, self.personID]

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
        return outputArray, handAccuaracyScore
    
    def getInfoText(self) -> str:
        handKeypoints = np.array(self.datum.handKeypoints)
        nbrPersonDetected = handKeypoints.shape[1] if handKeypoints.ndim >2 else 0

        self.infoText = ''
        self.infoText += str(nbrPersonDetected) + (' person detected' if nbrPersonDetected<2 else  ' person detected')

        if nbrPersonDetected > 0:
            leftHandDetected = (handKeypoints[0, self.personID].T[2].sum() > 1.0)
            rightHandDetected = (handKeypoints[1, self.personID].T[2].sum() > 1.0)
            if rightHandDetected and leftHandDetected:
                self.infoText += ', both hands of person ' + str(self.personID+1) + ' detected.'
            else:
                self.infoText += ', ' + ('Right' if rightHandDetected else 'Left') + ' hand of person ' + str(self.personID+1) + ' detected.'

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
        self.layout.addWidget(self.rawCamFeed,0,0,1,2)

        self.infoLabel = Qtw.QLabel('No info')
        self.layout.addWidget(self.infoLabel,1,1,1,1)

        self.pepperCamFeed = Qtw.QLabel(self)
        self.layout.addWidget(self.pepperCamFeed,0,2,1,1)

        self.simButton = SwitchButton()
        self.simButton.setChecked(True)
        #self.layout.addWidget(self.simButton,1,0,1,1)

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

class DatasetAcquisition(Qtw.QWidget):
    def __init__(self, parent):
        super().__init__( parent = parent)

        self.currentFolder = os.path.dirname(os.path.realpath(__file__))
        self.currentPoseName = 'Default'
        self.currentTresholdValue = .0
        ## Widgets initialisation
        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.folderLabel = ScrollLabel()
        self.folderLabel.setText(self.currentFolder)
        self.folderLabel.setMaximumHeight(50)
        self.folderLabel.setMinimumWidth(200)
        #self.folderLabel.setStyleSheet("background-color:#000000;")
        self.layout.addWidget(self.folderLabel, 0,0,1,5, Qt.AlignTop)

        self.folderButton = Qtw.QPushButton('Change folder')
        self.folderButton.clicked.connect(self.changeSavingFolder)
        self.layout.addWidget(self.folderButton, 0,5,1,1, Qt.AlignTop)

        self.handSelection = HandSelectionWidget(self)
        self.layout.addWidget(self.handSelection, 1,0,1,1)
        self.handSelection.changeHandSelection.connect(parent.changeHandID)

        self.layout.addWidget(Qtw.QLabel('Hand pose name:'), 1,1,1,1)
        self.poseNameLine = Qtw.QLineEdit(self.currentPoseName)
        self.layout.addWidget(self.poseNameLine, 1,2,1,1)
        self.poseNameLine.textChanged.connect(self.changePoseName)

        self.layout.addWidget(Qtw.QLabel('Accuaracy treshold:'), 1,3,1,1)
        self.tresholdValueLine = Qtw.QLineEdit(str(self.currentTresholdValue))
        onlyDouble = QDoubleValidator()
        self.tresholdValueLine.setValidator(onlyDouble)
        self.layout.addWidget(self.tresholdValueLine, 1,4,1,1)
        self.tresholdValueLine.textChanged.connect(self.changeTresholdValue)

        self.recordingButton = SwitchButton(self)
        self.recordingButton.setChecked(False)
        self.layout.addWidget(self.recordingButton,1,5,1,1)

        #verticalSpacer = Qtw.QSpacerItem(0, 0, Qtw.QSizePolicy.Minimum, Qtw.QSizePolicy.Expanding)
        #self.layout.addItem(verticalSpacer, 2, 0, Qt.AlignTop)
    
    @pyqtSlot()
    def changeSavingFolder(self):
        self.currentFolder = str(Qtw.QFileDialog.getExistingDirectory(self, "Select Directory"))
        self.folderLabel.setText(self.currentFolder)
    
    @pyqtSlot(str)
    def changePoseName(self, name:str):
        self.currentPoseName = name
    
    @pyqtSlot(str)
    def changeTresholdValue(self, value:str):
        try:
            self.currentTresholdValue = float(value.replace(',','.'))
        except:
            self.currentTresholdValue = .0

    def getSavingFolder(self)-> str:
        return self.currentFolder

    def getPoseName(self)->str:
        return self.currentPoseName
    
    def getTresholdValue(self)->float:
        return self.currentTresholdValue

    def resizeEvent(self, event):
        self.folderButton.setFixedHeight(self.folderLabel.height())

class DatasetLoading(Qtw.QWidget):
    def __init__(self, parent):
        super().__init__( parent = parent)
        self.parent = parent
        self.currentFilePath = ''
        self.datasetList = None
        self.accuracyList = None
        self.currentDataIndex = 0

        ## Widgets initialisation
        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.fileLabel = ScrollLabel()
        self.fileLabel.setText('No file selected')
        self.fileLabel.setMaximumHeight(50)
        self.fileLabel.setMinimumWidth(200)
        self.layout.addWidget(self.fileLabel, 0,0,1,6, Qt.AlignTop)

        self.fileButton = Qtw.QPushButton('Open file')
        self.fileButton.clicked.connect(self.loadFile)
        self.layout.addWidget(self.fileButton, 0,7,1,1, Qt.AlignTop)

        self.visuCheckbox = Qtw.QCheckBox('Visualize imported dataset')
        self.layout.addWidget(self.visuCheckbox,1,0)
        self.visuCheckbox.toggled.connect(self.visuCheckboxToggled)
        self.visuCheckbox.setEnabled(False)

        self.minusButton = Qtw.QToolButton()
        self.minusButton.setArrowType(Qt.LeftArrow)
        self.layout.addWidget(self.minusButton, 1,1,1,1)
        self.minusButton.setEnabled(False)
        self.minusButton.clicked.connect(lambda: self.setCurrentDataIndex(self.currentDataIndex-1))

        self.currentIndexLine = Qtw.QLineEdit(str(self.currentDataIndex))
        self.currentIndexLine.setValidator(QDoubleValidator())
        self.currentIndexLine.setMaximumWidth(25)
        self.currentIndexLine.setEnabled(False)
        self.layout.addWidget(self.currentIndexLine, 1,2,1,1)
        self.currentIndexLine.textChanged.connect(self.userIndexInput)

        self.maxIndexLabel = Qtw.QLabel(r'/0')
        self.maxIndexLabel.setEnabled(False)
        self.layout.addWidget(self.maxIndexLabel, 1,3,1,1)
        
        self.plusButton = Qtw.QToolButton()
        self.plusButton.setArrowType(Qt.RightArrow)
        self.layout.addWidget(self.plusButton, 1,4,1,1)
        self.plusButton.setEnabled(False)
        self.plusButton.clicked.connect(lambda: self.setCurrentDataIndex(self.currentDataIndex+1))

        horSpacer = Qtw.QSpacerItem(0, 0, Qtw.QSizePolicy.Expanding, Qtw.QSizePolicy.Minimum)
        self.layout.addItem(horSpacer, 1, 5)


    def userIndexInput(self, indexStr:str):
        if indexStr.isdigit():
            self.setCurrentDataIndex(int(indexStr))
        elif len(indexStr) == 0:
            pass
        else:
            self.currentIndexLine.setText(str(self.currentDataIndex))

    def visuCheckboxToggled(self, state:bool):
        self.parent.realTimeHandDraw_Signal.emit(not state)
        if state:
            self.setCurrentDataIndex(0)
            self.plusButton.setEnabled(True)
            self.minusButton.setEnabled(True)
            self.currentIndexLine.setEnabled(True)
            self.maxIndexLabel.setEnabled(True)

    def loadFile(self):
        options = Qtw.QFileDialog.Options()
        fileName, _ = Qtw.QFileDialog.getOpenFileName(self,"Open dataset", "","Text Files (*.txt)", options=options)
        self.datasetList = []
        self.accuracyList = []
        currentEntry = []

        if fileName:
            self.currentFile = fileName
            dataFile = open(self.currentFile)

            for i, line in enumerate(dataFile):
                if i == 0:
                    info = line.split(',')
                    if len(info) == 3:
                        poseName = info[0]
                        handID = int(info[1])
                        tresholdValue = float(info[2])
                    else:
                        self.fileLabel.setText('Not a supported dataset')
                        break
                else:
                    
                    if line[0] == '#' and line[1] != '#': # New entry
                        currentEntry = [[], [], []]

                        accuracy = float(line[1:])
                        self.accuracyList.append(accuracy)
                    
                    elif line[0] == 'x':
                        listStr = line[2:].split(' ')
                        for value in listStr:
                            currentEntry[0].append(float(value))
                    elif line[0] == 'y':
                        listStr = line[2:].split(' ')
                        for value in listStr:
                            currentEntry[1].append(float(value))
                    elif line[0] == 'a':
                        listStr = line[2:].split(' ')
                        for value in listStr:
                            currentEntry[2].append(float(value))
                        
                        self.datasetList.append(currentEntry)
            dataFile.close()
            self.maxIndexLabel.setText('/'+str(len(self.datasetList)))
            self.visuCheckbox.setEnabled(True)
            self.fileLabel.setText(self.currentFile + '\n  -> {} entries for {} ({} hand) with a minimum accuracy of {}.'.format(str(len(self.datasetList)), poseName, ('right' if handID==1 else 'left'), tresholdValue))
            return True
        return False
    
    def setCurrentDataIndex(self, index:int):
        
        if index > len(self.datasetList)-1:
            index = 0
        if index < 0:
            index = len(self.datasetList)-1
        self.currentDataIndex = index
        self.parent.drawHand(np.array(self.datasetList[self.currentDataIndex]), self.accuracyList[self.currentDataIndex])
        self.currentIndexLine.setText(str(self.currentDataIndex))
    
    def resizeEvent(self, event):
        self.fileButton.setFixedHeight(self.fileLabel.height())


class HandSelectionWidget(Qtw.QWidget):
    changeHandSelection = pyqtSignal(int)
    def __init__(self, parent = None):
        super(HandSelectionWidget, self).__init__(parent)
        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)
        self.parent = parent

        self.layout.addWidget(Qtw.QLabel('Hand focus:'),0,0)
        self.rightCheckbox = Qtw.QCheckBox('Right')
        self.leftCheckbox = Qtw.QCheckBox('Left')
        self.layout.addWidget(self.leftCheckbox,0,1)
        self.layout.addWidget(self.rightCheckbox,0,2)

        horSpacer = Qtw.QSpacerItem(0, 0, Qtw.QSizePolicy.Expanding, Qtw.QSizePolicy.Minimum)
        self.layout.addItem(horSpacer, 0, 3)

        self.rightCheckbox.toggled.connect(lambda check: self.leftCheckbox.setChecked(not check))
        self.leftCheckbox.toggled.connect(lambda check: self.rightCheckbox.setChecked(not check))
        self.rightCheckbox.toggled.connect(lambda check: self.changeHandSelection.emit(1 if check else 0))

        self.rightCheckbox.setChecked(True)


class TrainingWidget(Qtw.QWidget):
    realTimeHandDraw_Signal = pyqtSignal(bool)

    def __init__(self, parent = None):
        super(TrainingWidget, self).__init__(parent)

        ## Parameters
        self.dataNumber = 0
        self.currentFile = None
        self.handID = 1
        self.tresholdValue = .0
        self.isRecording = False
        self.layout=Qtw.QGridLayout(self)
        self.layout.setColumnStretch(1,2)
        self.setLayout(self.layout)
        self.parent = parent
        self.realTimeHandDraw = True
        self.realTimeHandDraw_Signal.connect(self.changeHandDrawingState)

        ## Widgets
        self.videoViewer = VideoViewer()
        self.layout.addWidget(self.videoViewer,0,0,1,1)
        
        self.acquisitionTab = DatasetAcquisition(self)
        self.loadingTab = DatasetLoading(self)
        self.dataTabs = Qtw.QTabWidget()
        self.dataTabs.addTab(self.acquisitionTab, 'New dataset')
        self.dataTabs.addTab(self.loadingTab, 'Loading dataset')
        self.layout.addWidget(self.dataTabs,2,0,1,1)
        self.acquisitionTab.recordingButton.clicked.connect(self.startStopRecording)

        self.cameraInput = CameraInput()

        videoHeight = 480 # 480p
        self.AnalysisThread = VideoAnalysisThread(self.cameraInput)
        self.AnalysisThread.newPixmap.connect(self.videoViewer.setImage)
        self.AnalysisThread.newPixmap.connect(self.analyseNewImage)
        self.AnalysisThread.setResolutionStream(int(videoHeight * (16.0/9.0)), videoHeight)
        self.videoViewer.setVideoSize(int(videoHeight * (16.0/9.0)), videoHeight)

        self.AnalysisThread.start()
        self.AnalysisThread.setState(True)
        self.videoViewer.simButton.clickedChecked.connect(self.AnalysisThread.setState)

        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setBackground('w')
        self.graphWidget.setXRange(-1.0, 1.0)
        self.graphWidget.setYRange(-1.0, 1.0)
        #self.graphWidget.setMinimumSize(videoHeight,videoHeight)
        self.graphWidget.setAspectLocked(True)
        self.layout.addWidget(self.graphWidget, 0,1,3,1)
    
    def analyseNewImage(self, image): # Call each time AnalysisThread emit a new pix
        handKeypoints, accuracy = self.AnalysisThread.getHandData(self.handID)
        
        self.videoViewer.setInfoText(self.AnalysisThread.getInfoText())
        
        if self.realTimeHandDraw:
            self.drawHand(handKeypoints, accuracy)

        if type(handKeypoints) != type(None): # If selected hand detected

            if self.isRecording:
                if accuracy > self.tresholdValue:
                    self.writeData(handKeypoints, accuracy)
                    print('.',end='')
    
    def drawHand(self, handKeypoints:np.ndarray, accuracy:float):
        self.graphWidget.clear()
        self.graphWidget.setTitle('Detection accuracy: ' + str(accuracy))
        if type(handKeypoints) != type(None):
            colors = ['r','y','g','b','m']
            data = [handKeypoints[:, 0:5],
                    np.insert(handKeypoints[:, 5:9].T, 0, handKeypoints[:,0], axis=0).T,
                    np.insert(handKeypoints[:, 9:13].T, 0, handKeypoints[:,0], axis=0).T,
                    np.insert(handKeypoints[:, 13:17].T, 0, handKeypoints[:,0], axis=0).T,
                    np.insert(handKeypoints[:, 17:21].T, 0, handKeypoints[:,0], axis=0).T]
            for i in range(len(data)):
                print(data[i])
                self.graphWidget.plot(data[i][0], data[i][1], symbol='o', symbolSize=7, symbolBrush=(colors[i]))
    
    def changeHandID(self, i:int):
        self.handID = i
    
    def startStopRecording(self, start:True):
        if start: #Start recording
            self.isRecording = True
            path = self.acquisitionTab.getSavingFolder()
            folder = self.acquisitionTab.getPoseName()
            self.tresholdValue = self.acquisitionTab.getTresholdValue()

            path += '\\' + folder
            if not os.path.isdir(path): #Create pose directory if missing
                os.mkdir(path)

            path += '\\' + ('right_hand' if self.handID == 1 else 'left_hand')
            if os.path.isdir(path):
                print('Directory allready exists.')
                self.isRecording = False
                self.acquisitionTab.recordingButton.setChecked(False)
            else:
                os.mkdir(path) #Create hand directory if missing
            
            if self.isRecording:
                self.currentFile = open(path + '\data.txt',"w+")
                self.currentFile.write(folder + ',' + str(self.handID) + ',' + str(self.tresholdValue) + '\n')
                self.currentFile.write('## Data generated the ' + str(date.today()) + ' labelled ' + folder + ' (' + ('right hand' if self.handID == 1 else 'left hand') + ') with a global accuracy higher than ' + str(self.tresholdValue) + ', based on OpenPose estimation.\n')
                self.currentFile.write('## Data format: Coordinates x, y and accuracy of estimation a\n\n')
                '''
                self.currentFile.write('## #i GlobalAccuracy\n')
                self.currentFile.write('## x0 x1 x2 ... x20\n')
                self.currentFile.write('## y0 y1 y2 ... y20\n')
                self.currentFile.write('## a0 a1 a2 ... a20\n\n')
                '''
                self.dataNumber = 0

        else: #Stop recording
            self.isRecording = False
            self.currentFile.close()
            self.currentFile = None
            print('File closed.')
    
    def writeData(self, handKeypoints, accuracy):
        self.dataNumber += 1
        self.currentFile.write('#' + str(accuracy))
        for i,row in enumerate(handKeypoints):
            for j,val in enumerate(row):
                self.currentFile.write('\n{}:'.format(['x','y','a'][i]) if j == 0 else ' ')
                self.currentFile.write(str(val))
        self.currentFile.write('\n\n')
    
    def changeHandDrawingState(self, state:bool):
        self.realTimeHandDraw = state

if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    import sys

    app = Qtw.QApplication(sys.argv)
    
    trainingWidget = TrainingWidget()
    trainingWidget.show()

    


    sys.exit(app.exec_())