import numpy as np
import cv2
from VideoAnalysis import VideoAnalysisThread, HandAnalysis
from Util import isHandData

class VideoInput:
    def __init__(self, urlVideo:str):
        self.video = cv2.VideoCapture(urlVideo)
        self.frame_width = int(self.video.get(3))
        self.frame_height = int(self.video.get(4))
        self.lastRet = True

    def getFPS(self):
        (major_ver, minor_ver, subminor_ver) = (cv2.__version__).split('.')
        if int(major_ver)  < 3 :
            fps = self.video.get(cv2.cv.CV_CAP_PROP_FPS)
        else :
            fps = self.video.get(cv2.CAP_PROP_FPS)
        return fps       

    def getHeight(self)->int:
        return self.frame_height

    def getWidth(self)->int:
        return self.frame_width 

    def getLastFrame(self):
        self.lastRet, frame = self.video.read()
        if self.lastRet:
            return frame
        else:
            print('Finished')
            return None
        
    def isOpened(self)->bool:
        return self.video.isOpened() and self.lastRet
    
    def release(self):
        self.video.release()

class VideoWriter:
    def __init__(self):
        self.leftHandAnalysis = HandAnalysis(0, showInput=False)
        self.rightHandAnalysis = HandAnalysis(1, showInput=False)

        self.video = VideoInput('test.mp4')

        self.AnalysisThread = VideoAnalysisThread(self.video)
        self.AnalysisThread.newMat.connect(self.analyseNewImage)
        self.AnalysisThread.setResolutionStream(self.video.getWidth(), self.video.getHeight())

        self.out = cv2.VideoWriter('outpy.avi',cv2.VideoWriter_fourcc(*'MJPG'), self.video.getFPS(), (1920,1080))
        
        self.AnalysisThread.start()
        self.AnalysisThread.setState(True)

    def analyseNewImage(self, matImage:np.ndarray): # Call each time AnalysisThread emit a new pix
        self.out.write(matImage)
        '''
        leftHandKeypoints, leftAccuracy = self.AnalysisThread.getHandData(0)
        rightHandKeypoints, rightAccuracy = self.AnalysisThread.getHandData(1)
        poseKeypoints = self.AnalysisThread.getBodyData()
        raisingLeft, raisingRight = self.AnalysisThread.isRaisingHand()

        self.leftHandAnalysis.updatePredictedClass(leftHandKeypoints)
        self.rightHandAnalysis.updatePredictedClass(rightHandKeypoints)

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1
        color = (255, 0, 255)
        print('Left:' + self.leftHandAnalysis.getCurrentPrediction())
        print('Right:' + self.rightHandAnalysis.getCurrentPrediction())

        if isHandData(leftHandKeypoints):
            position = (poseKeypoints[7][0],poseKeypoints[7][1]) # (0,0) <=> left-up corner
            cv2.putText(matImage, self.leftHandAnalysis.getCurrentPrediction(), position, font, scale, color, 2, cv2.LINE_AA)
        if isHandData(rightHandKeypoints):
            position = (poseKeypoints[4][0],poseKeypoints[4][1]) # (0,0) <=> left-up corner
            cv2.putText(matImage, self.rightHandAnalysis.getCurrentPrediction(), position, font, scale, color, 2, cv2.LINE_AA)
        
        #print(matImage)
        self.out.write(matImage)
        '''
    
    def release(self):
        self.video.release()
        self.out.release()
        
if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    from PyQt5 import QtWidgets as Qtw

    import sys
    app = Qtw.QApplication(sys.argv)

    videoWriter = VideoWriter()

    while(videoWriter.video.isOpened()):
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()