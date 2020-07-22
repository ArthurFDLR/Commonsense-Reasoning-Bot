from Util import SwitchButton, ScrollLabel
import queue
import time
from datetime import date
import cv2
import sys
import os
import pyqtgraph as pg
import numpy as np

from PyQt5 import QtWidgets as Qtw
from PyQt5.QtCore import Qt, QThread,  pyqtSignal, pyqtSlot, QSize
from PyQt5.QtGui import QImage, QPixmap, QDoubleValidator, QColor, QIcon
from PyQt5.QtMultimedia import QCameraInfo, QCamera, QCameraImageCapture
from PyQt5.QtMultimediaWidgets import QCameraViewfinder

# Path to OpenPose installation folder on your system.
openposePATH = r'C:\OpenPose'

sys.path.append(openposePATH + r'\build\python\openpose\Release')
releasePATH = r'C:\OpenPose\build\x64\Release'
binPATH = openposePATH + r'\build\bin'
modelsPATH = openposePATH + r'\models'
os.environ['PATH'] = os.environ['PATH'] + ';' + releasePATH + ';' + binPATH + ';'
import pyopenpose as op


class CameraInput(Qtw.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(CameraInput, self).__init__(*args, **kwargs)

        self.available_cameras = QCameraInfo.availableCameras()
        
        if not self.available_cameras:
            print('No camera')
            pass #quit

        self.lastImage = QImage('.\\Data\\tempInit.png')
        self.lastID = None
        self.save_path = ""

        self.select_camera(0)
    
    def refreshCameraList(self):
        self.available_cameras = QCameraInfo.availableCameras()
        if not self.available_cameras:
            print('No camera')
            return None
        self.camera.stop()
        self.select_camera(0)
        return self.available_cameras

    def getAvailableCam(self):
        return self.available_cameras

    def select_camera(self, i):
        self.camera = QCamera(self.available_cameras[i])
        self.camera.setCaptureMode(QCamera.CaptureStillImage)
        self.camera.start()

        self.capture = QCameraImageCapture(self.camera)
        self.capture.setCaptureDestination(QCameraImageCapture.CaptureToBuffer)

        self.capture.imageCaptured.connect(self.storeLastFrame)

        self.current_camera_name = self.available_cameras[i].description()
        self.save_seq = 0

    def getLastFrame(self):
        imageID = self.capture.capture()
        return self.qImageToMat(self.lastImage)
    
    def storeLastFrame(self, idImg:int, preview:QImage):
        self.lastImage = preview
        self.lastID = idImg

    def qImageToMat(self,incomingImage):
        url = '.\\Data\\temp.png'
        incomingImage.save(url, 'png')
        mat = cv2.imread(url)
        return mat


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
                        frame = self.resizeCvFrame(frame, 0.5)
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
    
    def resizeCvFrame(self, frame, ratio:float):
        width = int(frame.shape[1] * ratio) 
        height = int(frame.shape[0] * ratio) 
        dim = (width, height) 
        # resize image in down scale
        resized = cv2.resize(frame, dim, interpolation = cv2.INTER_AREA) 
        return resized


class VideoViewer(Qtw.QGroupBox):
    changeCameraID_signal = pyqtSignal
    def __init__(self, availableCameras):
        super().__init__('Camera feed')

        self.availableCameras = availableCameras

        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.rawCamFeed = Qtw.QLabel(self)
        self.layout.addWidget(self.rawCamFeed,0,0,1,3)

        self.infoLabel = Qtw.QLabel('No info')
        self.layout.addWidget(self.infoLabel,1,2,1,1)

        self.simButton = SwitchButton()
        self.simButton.setChecked(True)
        #self.layout.addWidget(self.simButton,1,0,1,1)

        self.refreshButton = Qtw.QPushButton('Refresh camera list')
        self.layout.addWidget(self.refreshButton, 1,0,1,1)

        self.camera_selector = Qtw.QComboBox()
        self.camera_selector.addItems([c.description() for c in self.availableCameras])
        self.layout.addWidget(self.camera_selector,1,1,1,1)

        self.autoAdjustable = False

    @pyqtSlot(QImage)
    def setImage(self, image):
        self.currentPixmap = QPixmap.fromImage(image)
        self.rawCamFeed.setPixmap(self.currentPixmap.scaled(self.rawCamFeed.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
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


class CreateDatasetDialog(Qtw.QDialog):
    def __init__(self, parent = None):
        super(CreateDatasetDialog, self).__init__(parent = parent)
        
        self.setWindowTitle("Create new dataset")

        self.currentFolder = os.path.dirname(os.path.realpath(__file__))
        self.currentFilePath = None
        self.currentPoseName = 'Default'
        self.currentTresholdValue = .0
        ## Widgets initialisation
        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.folderLabel = ScrollLabel()
        self.folderLabel.setText(self.currentFolder)
        self.folderLabel.setMaximumHeight(35)
        self.folderLabel.setMinimumWidth(200)
        #self.folderLabel.setStyleSheet("background-color:#000000;")
        self.layout.addWidget(self.folderLabel, 0,0,1,5, Qt.AlignTop)

        self.folderButton = Qtw.QPushButton('Change root folder')
        self.folderButton.clicked.connect(self.changeSavingFolder)
        self.layout.addWidget(self.folderButton, 0,5,1,1, Qt.AlignTop)

        self.handSelection = HandSelectionWidget(self)
        self.layout.addWidget(self.handSelection, 1,0,1,1)
        #self.handSelection.changeHandSelection.connect(parent.changeHandID)

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

        self.createButton = Qtw.QPushButton('Create dataset')
        self.layout.addWidget(self.createButton,1,5,1,1)
        self.createButton.clicked.connect(self.createDataset)
        #verticalSpacer = Qtw.QSpacerItem(0, 0, Qtw.QSizePolicy.Minimum, Qtw.QSizePolicy.Expanding)
        #self.layout.addItem(verticalSpacer, 2, 0, Qt.AlignTop)
    
    def createDataset(self):
        self.isRecording = True

        path = self.getSavingFolder()
        folder = self.getPoseName()
        tresholdValue = self.getTresholdValue()
        handID = self.handSelection.getCurrentHandID()

        path += '\\' + folder
        if not os.path.isdir(path): #Create pose directory if missing
            os.mkdir(path)

        path += '\\' + ('right_hand' if handID == 1 else 'left_hand')
        if os.path.isdir(path):
            print('Directory allready exists.')
            self.isRecording = False
            self.createButton.setEnabled(False)
            self.createButton.setText('Dataset allready created')

        else:
            self.createButton.setEnabled(True)
            self.createButton.setText('Create dataset')
            os.mkdir(path) #Create hand directory if missing

            path += '\data.txt'
            currentFile = open(path,"w+")
            currentFile.write(self.getFileHeadlines())
            currentFile.close()
            self.accept()
            self.currentFilePath = path
    
    def getFileHeadlines(self):
        path = self.getSavingFolder()
        folder = self.getPoseName()
        tresholdValue = self.getTresholdValue()
        handID = self.handSelection.getCurrentHandID()
        output = ''
        output += folder + ',' + str(handID) + ',' + str(tresholdValue) + '\n'
        output += '## Data generated the ' + str(date.today()) + ' labelled ' + folder + ' (' + ('right hand' if handID == 1 else 'left hand') + ') with a global accuracy higher than ' + str(tresholdValue) + ', based on OpenPose estimation.\n'
        output += '## Data format: Coordinates x, y and accuracy of estimation a\n\n'
        return output
    
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
    
    def getHandID(self)->int:
        return self.handSelection.getCurrentHandID()
    
    def getFilePath(self)->str:
        return self.currentFilePath

    def resizeEvent(self, event):
        self.folderButton.setFixedHeight(self.folderLabel.height())


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
    
    def getCurrentHandID(self):
        return 1 if self.rightCheckbox.isChecked() else 0


class DatasetController(Qtw.QWidget):
    realTimeHandDraw_Signal = pyqtSignal(bool)
    def __init__(self, parent):
        super().__init__( parent = parent)
        self.parent = parent
        self.currentFilePath = ''
        self.currentFileHeadLines = ''
        self.poseName = ''
        self.handID = 0
        self.tresholdValue = 0.0
        self.datasetList = []
        self.accuracyList = []
        self.currentDataIndex = 0

        ## Widgets initialisation
        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.fileLabel = ScrollLabel()
        self.fileLabel.setText('No file selected')
        self.fileLabel.setMaximumHeight(50)
        self.fileLabel.setMinimumWidth(180)
        self.layout.addWidget(self.fileLabel, 0,0,1,8, Qt.AlignTop)

        #self.saveButton = Qtw.QPushButton('Save dataset')
        #self.layout.addWidget(self.saveButton, 0,7,1,1, Qt.AlignTop)
        #self.saveButton.clicked.connect(self.writeDataToTxt)

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

        self.deleteButton = Qtw.QPushButton('Delete entry')
        self.layout.addWidget(self.deleteButton, 1,5,1,1)
        self.deleteButton.clicked.connect(lambda: self.removeEntryDataset(self.currentDataIndex))


        self.recordButton = SwitchButton()
        self.recordButton.setChecked(False)
        self.layout.addWidget(self.recordButton,1,7,1,1)
        self.recordButton.clickedChecked.connect(self.startRecording)

        horSpacer = Qtw.QSpacerItem(0, 0, Qtw.QSizePolicy.Expanding, Qtw.QSizePolicy.Minimum)
        self.layout.addItem(horSpacer, 1, 6)
    
    def addEntryDataset(self, keypoints, accuracy:float):
        ''' Add keypoints and accuracy of a hand pose to the local dataset.
        
        Args:
            keypoints (np.ndarray((3,21),float)): Coordinates x, y and the accuracy score for each 21 key points.
            accuracy (float): Global accuracy of detection of the pose.
        '''
        self.datasetList.append(keypoints)
        self.accuracyList.append(accuracy)
        self.maxIndexLabel.setText('/'+str(len(self.accuracyList)))
    
    def removeEntryDataset(self, index:int):
        ''' Remove keypoints and accuracy referenced by its index from the local dataset.
        
        Args:
            index (int): Index in list of the entry removed.
        '''
        self.datasetList = self.datasetList[:index] + self.datasetList[index+1:]
        self.accuracyList = self.accuracyList[:index] + self.accuracyList[index+1:]
        maxIndex = len(self.accuracyList)
        self.maxIndexLabel.setText('/'+str(maxIndex))
        index = min(index, maxIndex-1)
        self.setCurrentDataIndex(index)
        #self.currentIndexLine.setText(str(self.currentDataIndex + 1))
        #self.parent.drawHand(np.array(self.datasetList[index]), self.accuracyList[index])
    
    def clearDataset(self):
        self.datasetList = []
        self.accuracyList = []

    def userIndexInput(self, indexStr:str):
        if indexStr.isdigit():
            self.setCurrentDataIndex(int(indexStr)-1)
        elif len(indexStr) == 0:
            pass
        else:
            self.currentIndexLine.setText(str(self.currentDataIndex + 1))

    def visuCheckboxToggled(self, state:bool):
        self.realTimeHandDraw_Signal.emit(not state)
        if state:
            self.setCurrentDataIndex(0)
            self.plusButton.setEnabled(True)
            self.minusButton.setEnabled(True)
            self.currentIndexLine.setEnabled(True)
            self.maxIndexLabel.setEnabled(True)

    def loadFile(self):
        options = Qtw.QFileDialog.Options()
        fileName, _ = Qtw.QFileDialog.getOpenFileName(self,"Open dataset", "","Text Files (*.txt)", options=options)
        self.clearDataset()
        currentEntry = []

        if fileName:
            dataFile = open(fileName)
            fileHeadline = ''
            for i, line in enumerate(dataFile):
                if i == 0:
                    info = line.split(',')
                    fileHeadline += line
                    if len(info) == 3:
                        poseName = info[0]
                        handID = int(info[1])
                        tresholdValue = float(info[2])
                    else:
                        self.fileLabel.setText('Not a supported dataset')
                        break
                else:
                    if line[0] == '#' and line[1] == '#': # Commentary/headlines
                        fileHeadline += line
                    elif line[0] == '#' and line[1] != '#': # New entry
                        currentEntry = [[], [], []]
                        accuracy = float(line[1:])
                    elif line[0] == 'x':
                        listStr = line[2:].split(' ')
                        for value in listStr:
                            currentEntry[0].append(float(value))
                    elif line[0] == 'y':
                        listStr = line[2:].split(' ')
                        for value in listStr:
                            currentEntry[1].append(float(value))
                    elif line[0] == 'a':  # Last line of entry
                        listStr = line[2:].split(' ')
                        for value in listStr:
                            currentEntry[2].append(float(value))
                        self.addEntryDataset(currentEntry, accuracy)

            dataFile.close()
            self.updateFileInfo(fileName, fileHeadline, len(self.datasetList), poseName, handID, tresholdValue)
            return True
        return False
    
    def updateFileInfo(self, filePath:str=None, fileHead:str=None, sizeData:int = 0, poseName:str=None, handID:int=None, tresholdValue:int=None):
        self.visuCheckbox.setEnabled(True)
        if filePath:
            print('yo')
            self.currentFilePath = filePath
        if fileHead:
            self.currentFileHeadLines = fileHead
        if poseName:
            self.poseName = poseName
        if handID != None:
            self.handID = handID
        if tresholdValue != None:
            self.tresholdValue = tresholdValue
        self.fileLabel.setText(self.currentFilePath + '\n  -> {} entries for {} ({} hand) with a minimum accuracy of {}.'.format(str(sizeData), poseName, ('right' if handID==1 else 'left'), str(tresholdValue)))
        self.maxIndexLabel.setText('/'+str(sizeData))

    def setCurrentDataIndex(self, index:int):
        if len(self.datasetList) == 0:
            self.currentDataIndex = 0
            self.parent.drawHand(None, 0.0)
        else:
            if index >= len(self.datasetList):
                index = 0
            if index < 0:
                index = len(self.datasetList)-1
            self.currentDataIndex = index

            self.parent.drawHand(np.array(self.datasetList[self.currentDataIndex]), self.accuracyList[self.currentDataIndex])
        self.currentIndexLine.setText(str(self.currentDataIndex + 1))
        
    def writeDataToTxt(self):
        ''' Save the current dataset to the text file (URL: self.currentFilePath).'''
        print('Saving dataset ...')
        dataFile = open(self.currentFilePath, 'w') #Open in write 'w' to clear.
        dataFile.write(self.currentFileHeadLines)
        sizeData = len(self.datasetList)
        for entryIndex in range(sizeData):
            dataFile.write('#' + str(self.accuracyList[entryIndex]))
            for i,row in enumerate(self.datasetList[entryIndex]):
                for j,val in enumerate(row):
                    dataFile.write('\n{}:'.format(['x','y','a'][i]) if j == 0 else ' ')
                    dataFile.write(str(val))
            dataFile.write('\n\n')
        self.updateFileInfo(sizeData=sizeData)
    
    def startRecording(self, state:bool):
        self.parent.isRecording = state


class TrainingWidget(Qtw.QMainWindow):
    def __init__(self, parent = None):
        ## Init
        super(TrainingWidget, self).__init__(parent)
        self.setWindowTitle("Hand pose classifier")
        self.parent = parent
        mainWidget = Qtw.QWidget(self)
        self.setCentralWidget(mainWidget)
        self.layout=Qtw.QGridLayout(mainWidget)
        self.layout.setColumnStretch(1,2)
        mainWidget.setLayout(self.layout)

        ## Parameters
        self.handID = 1
        self.tresholdValue = .0
        self.isRecording = False
        self.realTimeHandDraw = True

        ## Menu

        bar = self.menuBar()
        fileAction = bar.addMenu("Dataset")
        fileAction.addAction("Open")
        fileAction.addAction("Create")
        fileAction.addAction("Save")
        fileAction.triggered[Qtw.QAction].connect(self.processtrigger)
 
        ## Widgets
        self.cameraInput = CameraInput()

        self.videoViewer = VideoViewer(self.cameraInput.getAvailableCam())
        self.videoViewer.camera_selector.currentIndexChanged.connect(self.cameraInput.select_camera)
        self.videoViewer.refreshButton.clicked.connect(self.refreshCameraList)
        self.layout.addWidget(self.videoViewer,0,0,1,1)
        
        self.datasetController = DatasetController(self)
        self.layout.addWidget(self.datasetController,1,0,1,1)
        self.datasetController.realTimeHandDraw_Signal.connect(self.changeHandDrawingState)

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
    
    def refreshCameraList(self):
        print('Refresh cam list')
        camList = self.cameraInput.refreshCameraList()
        if not camList:
            print('No camera')
        else:
            self.videoViewer.camera_selector.clear()
            self.videoViewer.camera_selector.addItems([c.description() for c in camList])

    def processtrigger(self,q):

        print(q.text())
        if (q.text() == "Open"):
            self.datasetController.loadFile()
                
        if q.text() == "Create":
            dlg = CreateDatasetDialog(self)
            if dlg.exec_():
                print("Success!")
                self.datasetController.updateFileInfo(dlg.getFilePath(), dlg.getFileHeadlines(), 0, dlg.getPoseName(), dlg.getHandID(), dlg.getTresholdValue())
            else:
                print("Cancel!")
                
        if q.text() == "Save":
            self.datasetController.writeDataToTxt()

    def analyseNewImage(self, image): # Call each time AnalysisThread emit a new pix
        handKeypoints, accuracy = self.AnalysisThread.getHandData(self.handID)
        
        self.videoViewer.setInfoText(self.AnalysisThread.getInfoText())
        
        if self.realTimeHandDraw:
            self.drawHand(handKeypoints, accuracy)

        if type(handKeypoints) != type(None): # If selected hand detected
            #print(handKeypoints)
            if self.isRecording:
                if accuracy > self.tresholdValue:
                    self.datasetController.addEntryDataset(handKeypoints, accuracy)
                    #self.writeData(handKeypoints, accuracy)
    
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
                #print(data[i])
                self.graphWidget.plot(data[i][0], data[i][1], symbol='o', symbolSize=7, symbolBrush=(colors[i]))
    
    def changeHandID(self, i:int):
        self.handID = i
    
    def changeHandDrawingState(self, state:bool):
        self.realTimeHandDraw = state

if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    import sys

    app = Qtw.QApplication(sys.argv)
    
    trainingWidget = TrainingWidget()
    trainingWidget.show()

    sys.exit(app.exec_())