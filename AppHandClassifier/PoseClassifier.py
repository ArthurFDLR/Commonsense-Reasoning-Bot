import os
#os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' #Avoid the annoying tf warnings 

import tensorflow as tf
import numpy as np
import math

def loadFile(poseName:str, handID:int):
    fileName = '.\\Datasets\\{}\\{}\\data.txt'.format(poseName, 'right_hand' if handID == 1 else 'left_hand')
    listOut = []
    if os.path.exists(fileName):

        currentEntry = []

        dataFile = open(fileName)
        for i, line in enumerate(dataFile):
            if i == 0:
                info = line.split(',')
                if len(info) == 3:
                    poseName = info[0]
                    handID = int(info[1])
                    tresholdValue = float(info[2])
                else:
                    print('Not a supported dataset')
                    break
            else:
                if line[0] == '#' and line[1] != '#': # New entry
                    currentEntry = [[], []]
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
                    listOut.append([])
                    for i in range(len(currentEntry[0])):
                        listOut[-1].append(currentEntry[0][i])
                        listOut[-1].append(currentEntry[1][i])

        dataFile.close()

    return listOut

def saveModel(model:tf.keras.models, name:str, handID:int, outputClass):
    rootPath = r'.\Models'
    if not os.path.isdir(rootPath): #Create Models directory if missing
        os.mkdir(rootPath)
    modelPath = rootPath + r".\\" + name
    if not os.path.isdir(modelPath): #Create model directory if missing
        os.mkdir(modelPath)
    
    classFile = open(modelPath+r'\class.txt',"w")
    for i,c in enumerate(outputClass):
        classFile.write((',' if i!=0 else '') + c)
    classFile.close()

    model.save( modelPath + r'\\' + name + ('_right' if handID == 1 else '_left') + '.h5')



if __name__ == "__main__":
    ## Load datasets (Only right hand)
    classOutput = ['Chef', 'Help', 'VIP', 'Water']
    allSamples_x = []
    allSamples_y = []
    allSamples_y_oneHot = []
    handID = 0
    for i, className in enumerate(classOutput):
        loadedSampels = loadFile(className, handID)
        allSamples_x += loadedSampels
        allSamples_y += [i for j in range(len(loadedSampels))]
        outPut_tmp = [0]*len(classOutput)
        outPut_tmp[i] = 1
        allSamples_y_oneHot += [outPut_tmp for j in range(len(loadedSampels))]
    

    ## Shuffle lists
    allSamples_x = np.array(allSamples_x)
    allSamples_y = np.array(allSamples_y)
    allSamples_y_oneHot = np.array(allSamples_y_oneHot)

    index = np.arange(allSamples_x.shape[0])
    np.random.shuffle(index)
    allSamples_x = allSamples_x[index]
    allSamples_y = allSamples_y[index]
    allSamples_y_oneHot = allSamples_y_oneHot[index]

    print(len(allSamples_y_oneHot))
    print(len(allSamples_y))

    inputSize = allSamples_x.shape[1] # (2 dimensions)*(21 keypoints) = 42

    sizeTrainSet = int(0.7 * allSamples_x.shape[0])
    trainSamples_x = allSamples_x[:sizeTrainSet]
    trainSamples_y = allSamples_y[:sizeTrainSet]
    testSamples_x  = allSamples_x[sizeTrainSet:]
    testSamples_y  = allSamples_y[sizeTrainSet:]

    
    ## Model definition

    model = tf.keras.models.Sequential()
    model.add(tf.keras.layers.Dense(32, input_dim=42, activation=tf.keras.activations.relu))
    model.add(tf.keras.layers.Dense(32, activation=tf.keras.activations.relu))
    model.add(tf.keras.layers.Dense(len(classOutput), activation=tf.keras.activations.softmax))

    model.summary()
    model.compile(optimizer=tf.keras.optimizers.Adam(),
                  loss='categorical_crossentropy', # prefere loss='sparse_categorical_crossentropy' if not one-hot encoded
                  metrics=['accuracy'])

    model.fit(x=allSamples_x, y=allSamples_y_oneHot, epochs=7, batch_size=20,  validation_split=0.15) #, validation_data=(testSamples_x, testSamples_y)

    saveModel(model, 'SimpleRestaurantSignals', handID, classOutput)
    #model.save(r'.\Models\FirstModel.h5')
