import fileinput
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
import time
import subprocess, re
import pathlib
FILE_PATH = pathlib.Path(__file__).parent.absolute()

class CommunicationAspThread(QThread):
    newObservation_signal = pyqtSignal(str, bool)
    newGoal_signal = pyqtSignal(str)

    def __init__(self, constantOrderList=None):
        """Communication thread with an ASP (Sparc) program. Call the ASP program and update orders list when a new observation is recorded.
        Observations are send through newObservaiton_signal.

        Args:
            constantOrderList ([], optional): Only use for testing purposes, desactivate ASP calls and initialize orders in memory. Defaults to None.
        """
        super().__init__()

        self.constantOrders = hasattr(constantOrderList, '__len__')
        if self.constantOrders:
            self.constantOrders = (len(constantOrderList) != 0)
        
        if self.constantOrders:
            self.stackOrders = constantOrderList
            print('Constant order list.')
        else:
            self.stackOrders = []

        self.state = False
        self.maxStepCounter = 0
        self.currentOrderStep = 0
        self.currentObsDict = {}
        self.currentHoldsList = []
        self.currentGoals = []
        self.currentInitSituation = []
        self.aspFilePath = FILE_PATH / 'ProgramASP.sparc'

        self.newObservation_signal.connect(self.newObservation)
        self.newGoal_signal.connect(self.newGoal)

        self.currentGoalStep = 0

        self.resetAll()
    
    def run(self):
        while True:
            if self.state:
                if len(self.currentObsDict) > 0: # If new observation received
                    time.sleep(0.3)
                    self.update()

                    #print(self.stackOrders, ' -> ' , self.getCurrentOrder())
    
    def setState(self, b:bool):
        ''' Activate or deactivate ASP computation.
        
        Args:
            b (bool): True -> Activate | False -> Deactivate
        '''
        self.state = b

    def resetMaxSteps(self):
        self.maxStepCounter = 0
        #self.clearObservations()
        self.writeStepsLimit(self.maxStepCounter)
    
    def getCurrentOrderStep(self):
        return self.currentOrderStep

    def update(self):
        ''' Call the ASP program (cf. aspFilePath) and update orders stack. '''
        print('Update ASP ',not self.constantOrders)
        if not self.constantOrders:
            print('Update ASP')

            self.updateInitSituation(self.currentGoalStep) #Update initial situation accordingly to orders achieved by the robot

            tmpStackOrder = self.stackOrders
            self.stackOrders = []
            self.writeObservations()
            self.writeGoals() #Add goals linked to new observations to the Sparc file
            self.maxStepCounter += 1
            self.writeStepsLimit(self.maxStepCounter + 8)
            self.currentObsDict = {}
            self.currentGoals = []
            self.currentInitSituation = []
            self.currentGoalStep = 0

            if not self.callASP(): #If ASP inconsistent
                self.stackOrders = tmpStackOrder
    
    def writeStepsLimit(self, n:int):
        ''' Change step limit in aspFilePath file.
        
        Args:
            n (int>0): New step limit 
        '''
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "#const nstep =" in line:
                line=line.replace(line, '#const nstep = {}.\n'.format(n))
            print(line,end='')
    
    def updateInitSituation(self, stepNbr:int):
        """ Finds what holds true at step stepNbr in self.currentHoldsList
        and writes the result as the new initial situation. """
        for i in range(len(self.currentHoldsList)):
                # This loop finds if the step at which a fluent holds true corresponds to
                # the step at which is the new initial situation to be updated
                temp = self.currentHoldsList[i]
                #print(temp)
                matches = re.finditer(r"(?:[^\,](?!(\,)))+$", temp)
                for matchNum, match in enumerate(matches, start = 1):
                    if int(temp[match.start():match.end()-1]) == stepNbr:
                        self.currentInitSituation.append(temp[:match.start()])
        return True

    def writeInitSituation(self, initSituation=None):
        ''' Writes new initial situation in ProgramASP SPARC file if different from the previous one. '''
        newInitSitStr = ''

        if hasattr(initSituation, '__len__'):
            for initSit in initSituation:
                newInitSitStr += 'holds(' + initSit + ', 0).\n'
        else:
            for initSit in self.currentInitSituation:
                newInitSitStr += initSit + '0).\n'

        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%e_init" in line:
                line=line.replace(line, newInitSitStr + line)
            print(line,end='')
        
    def writeGoals(self):
        newGoalStr = ''

        for goal in self.currentGoals:
            newGoalStr += 'goal(I):- holds(' + goal + ',I).\n'
        
        print('Write new goals: ', newGoalStr)
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%e_goal" in line:
                line=line.replace(line, newGoalStr + line)
            print(line,end='')

    def writeObservations(self):
        ''' Write observations stored in currentObsDict in aspFilePath file. '''
        newObsStr = ''
        for obs in self.currentObsDict.keys():
            newObsStr += 'obs(' + obs + ','
            newObsStr += 'true' if self.currentObsDict[obs] else 'false'
            newObsStr += ',' + str(self.maxStepCounter) + ').\n'
        
        print('Write new observations: ', newObsStr)
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%e_obs" in line:
                line=line.replace(line, newObsStr + line)
            print(line,end='')
    
    def resetAll(self):
        self.resetMaxSteps()
        self.clearGoals()
        self.clearInitSituation()
        self.clearObservations()

    def clearInitSituation(self):
        ''' Erase initial situations in aspFilePath file. '''
        initZone = False
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%b_init" in line:
                initZone = True
            if "%e_init" in line:
                initZone = False
            if not initZone or line[0] == '%':
                print(line,end='')
       
    def clearGoals(self):
        ''' Erase all goals in aspFilePath file. '''
        goalZone = False
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%b_goal" in line:
                goalZone = True
            if "%e_goal" in line:
                goalZone = False
            if not goalZone or line[0] == '%':
                print(line,end='')

    def clearObservations(self):
        ''' Erase all observations in aspFilePath file. '''
        obsZone = False
        for line in fileinput.FileInput(self.aspFilePath,inplace=1):
            if "%b_obs" in line:
                obsZone = True
            if "%e_obs" in line:
                obsZone = False
            if not obsZone or line[0] == '%':
                print(line,end='')

    def callASP(self):
        ## Formatting, running the command and retrieving, formatting the output
        output = subprocess.check_output('java -jar {} {} -A -n 1'.format(FILE_PATH/'sparc.jar',self.aspFilePath))
        output = str(output)
        outputList = re.findall(r"\{(.*?)\}", output)
        
        if len(outputList)>0:
            outputList = outputList[0].split(' ')

            orderList = []
            orderTransmit = []
            currentOrdDict = {}
            self.currentHoldsList = []
            initList = []

            goalList = []
            stepList = []

            for i in range(len(outputList)):
                if "occurs" in outputList[i] and not "-occurs" in outputList[i]:
                    if outputList[i][-1]==',': 
                        outputList[i]=outputList[i][:-1]
                    orderList.append(outputList[i])
                if "holds" in outputList[i] and not "-holds" in outputList[i]:
                    if outputList[i][-1]==',': 
                        outputList[i]=outputList[i][:-1]
                    self.currentHoldsList.append(outputList[i])
            if orderList != orderTransmit: 
                orderTransmit = orderList

            n = len(orderTransmit)

            for i in range(n):
                # This loop finds the step at which an order must be executed by the agent
                temp = orderTransmit[i][7:-1]
                matches = re.finditer(r"(?:[^\,](?!(\,)))+$", temp)
                for matchNum, match in enumerate(matches, start = 1):
                    currentOrdDict[temp[:match.start()-1]] = int(match.group())
            
            self.stackOrders = [key for (key, value) in sorted(currentOrdDict.items(), key=lambda x: x[1])]
            return True

            for i in range(len(outputList)):
                # This loops finds the step at which the goal is archieved, corresponding to the new initial situation
                if "goal" in outputList[i]: goalList.append(outputList[i])
            if len(goalList) > 0: 
                for in in range(len(goalList)):
                    stepList.append(int(re.findall(r"\((.*?)\)", goalList[i])[0]))
                stepList.sort()
            self.currentGoalStep = stepList[0]

        else:
            self.stackOrders = []
            print("The SPARC program is inconsistent.")
            return False
    
    @pyqtSlot(str)
    def newGoal(self, name:str):
        print('New goal: ' + name)
        self.currentGoals.append(name)

    @pyqtSlot(str, bool)
    def newObservation(self, name:str, state:bool):
        print('New Observation: ' + name)
        self.currentObsDict[name] = state
        #if 'bill_wave' in name:
        #    tableNum = name[15:-1]
        #    self.newGoal_signal.emit('haspaid(t{})'.format(tableNum))

    def getCurrentOrder(self)->str:
        if len(self.stackOrders) > self.currentOrderStep:
            return self.stackOrders[self.currentOrderStep]
        else:
            return None
    
    def currentOrderCompleted(self)->str:
        """Update orders list.

        Returns:
            str: New order in the list.
        """
        self.currentOrderStep += 1
        if len(self.stackOrders) > self.currentOrderStep:
            return self.stackOrders[self.currentOrderStep]
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
        while time.time() - t < 1.0: pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    app = Qtw.QApplication(sys.argv)
    aspThread = CommunicationAspThread()
    aspThread.start()
    aspThread.setState(False)

    aspThread.update()
    aspThread.updateInitSituation(aspThread.getCurrentOrderStep())
    print(aspThread.currentHoldsList)
    print(aspThread.currentInitSituation)
    print(aspThread.stackOrders)
    sys.exit(app.exec_())