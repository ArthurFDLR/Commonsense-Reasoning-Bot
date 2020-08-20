import fileinput
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
import time
import subprocess, shlex, re

class CommunicationAspThread(QThread):
    newObservation_signal = pyqtSignal(str, bool)
    def __init__(self):
        super().__init__()

        self.state = False
        #self.stepDuration = 0.5 # duration between two step (secondes)
        self.lastTime = time.time()
        self.stepCounter = 0
        self.currentObsDict = {}
        self.aspFilePath = 'ProgramASP.sparc'
        self.stackOrders = []

        self.newObservation_signal.connect(self.newObservation)
    
    def run(self):
        while True:
            if self.state:
                if len(self.currentObsDict) > 0: # If new observation received
                    time.sleep(0.3)
                    self.callASP()
                    print(self.getOrders())

    def setState(self, b:bool):
        ''' Activate or deactivate ASP computation.
        
        Args:
            b (bool): True -> Activate | False -> Deactivate
        '''
        self.stepCounter = 0
        self.state = b
    
    def callASP(self):
        ''' Call the ASP program (cf. aspFilePath) - update orders stack. '''
        self.stackOrders = []
        self.updateObservation()
        self.updateOrder()
        self.stepCounter += 1
        self.currentObsDict = {}
    
    def changeStepsLimit(self, n:int):
        ''' Change step limit in aspFilePath file.
        
        Args:
            n (int>0): New step limit 
        '''
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "#const n =" in line:
                line=line.replace(line, '#const n = {}.\n'.format(n))
            print(line,end='')

    def updateObservation(self):
        ''' Write new observations in aspFilePath file. '''
        newObsStr = ''
        for obs in self.currentObsDict.keys():
            newObsStr += 'obs(' + obs + ','
            newObsStr += 'true' if self.currentObsDict[obs] else 'false'
            newObsStr += ',' + str(self.stepCounter) + ').\n'
        
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%e_obs" in line:
                line=line.replace(line, newObsStr + line)
            print(line,end='')
    
    def clearObservation(self):
        ''' Erase all observations in aspFilePath file. '''
        obsZone = False
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%b_obs" in line:
                obsZone = True
            if "%e_obs" in line:
                obsZone = False
            if not obsZone or line[0] == '%':
                print(line,end='')

    def updateOrder(self):
        ## Command line to retrieve only 1 answer set ##
        self.orderCommand = 'java -jar sparc.jar {} -A -n 1'.format(self.aspFilePath)
        ## Filtering keyword to only retrieve actions to perform ##
        self.orderKeyword = 'occurs'

        self.orderTransmit = []

        ## Formatting, running the command and retrieving, formatting the output ##
        args = shlex.split(self.orderCommand)
        output = subprocess.check_output(args)
        output = str(output)
        outputList = re.findall('\{(.*?)\}', output)
        outputList = outputList[0].split(' ')

        orderList = []

        try : 
            for i in range(len(outputList)):
                if 'occurs' in outputList[i] and not '-occurs' in outputList[i]:
                    if outputList[i][-1]==',': 
                        outputList[i]=outputList[i][:-1]
                    orderList.append(outputList[i])
            if orderList != self.orderTransmit: self.orderTransmit = orderList
            #print('New orders received:')
            #print(self.orderTransmit)

            n = len(self.orderTransmit)

            orderList_formatted = [['', '']]*n

            for i in range(n):
                temp = self.orderTransmit[i][7:-1]
                matches = re.finditer(r"(?:[^\,](?!(\,)))+$", temp)
                for matchNum, match in enumerate(matches, start=1):
                    orderList_formatted[i][0] = temp[:match.start()-1]
                    orderList_formatted[i][1] = match.group()
            
            for i in range(n):
                currentOrdDict[orderList_formatted[i][0]] = int(orderList_formatted[i][1])
            
            self.stackOrders = [key for (key, value) in sorted(currentOrdDict.items(), key=lambda x: x[1])]

        except : print("The SPARC program is inconsistent.")

    @pyqtSlot(str, bool)
    def newObservation(self, name:str, state:bool):
        self.currentObsDict[name] = state
    
    def getCurrentOrders(self)->str:
        return self.stackOrders[0]
    
    def currentOrderCompleted(self)->str:
        self.stackOrders = self.stackOrders[1:]
        if len(self.stackOrders) > 0:
            return self.stackOrders[0]
        else:
            return None


if __name__ == "__main__":

    import sys
    from PyQt5 import QtWidgets as Qtw
    import signal

    def signal_handler(signal, frame):
        aspThread.setState(True)
        t = time.time()
        print('exit')
        while time.time() - t < 0.3: pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    app = Qtw.QApplication(sys.argv)
    aspThread = CommunicationAspThread()
    aspThread.start()
    lastTime = time.time()

    aspThread.clearObservation()

    aspThread.changeStepsLimit(10)

    aspThread.setState(True)

    while(True):
        if time.time() - lastTime > 0.3:
            lastTime = time.time()
            aspThread.newObservation_signal.emit("bill_wave(c1)", True)

    sys.exit(app.exec_())