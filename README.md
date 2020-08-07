# Robotics Vision Simulator

* [Hand pose classifier](#hand-pose-classifier)
  1. [OpenPose output](#1-openpose-output)
  2. [Keypoints normalization](#2-keypoints-normalization)
  3. [Dataset creation](#3-Dataset-creation---9809-samples-for-24-output-categories)
* [Simulated world - Human-robot collaboration](#Simulated-world)

## Hand pose classifier

This classifier is build upon the excellent pose estimator [**OpenPose**](https://github.com/CMU-Perceptual-Computing-Lab/openpose) from **CMU Perceptual Computing Lab**. A GUI has been developped to ease dataset creation and real-world testing. 

![Hand pose classifier GUI](/.github/markdown/GUI_HPC.png)

### 1. OpenPose output

The 21 hand keypoints (2D) used as input for this classifier are produced by OpenPose. The hand output format is as follow:

<img src="/.github/markdown/keypoints_hand.png" width="200">

More information can be found [here](https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/doc/output.md#face-and-hands). Please note that even if only hand keypoints are used, [OpenPose recquiered the whole body to be analysed](https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/doc/standalone_face_or_hand_keypoint_detector.md) in order to generate hand informations. Furtheremore keypoints coordinates are given in the frame of reference of the image feeded to OpenPose. Thus, the coordinates have to be normalized.
I addition to x, y coordinates, the accuracy of detection of each keypoints is provided. From now on, the sum of these values will be simply refered as accuracy.

### 2. Keypoints normalization

To prepare the data for the input of the neural network, coordinates are normalized relatively to finger length and the center of gravity of the hand.

* **Scaling:** First, the length of each fingers - defined as a set of lines of the same color, see above - is calculated. The euclidian distances of all segments of a finger are sumed *- e.g.* <img src="https://render.githubusercontent.com/render/math?math=Thumb\_length = \sum_{i=0}^{3} d(\boldsymbol{k_i}, \boldsymbol{k_{i%2B1}})">.
Then, every coordinates composing the hand are divided by the greater finger length.

* **Centering:** Keypoints are centered relatively to the center of mass of the hand which in this case, is simply defined as <img src="https://render.githubusercontent.com/render/math?math=(\bar{\boldsymbol{k^x}}, \bar{\boldsymbol{k^y}})">.

<details><summary>Click to show code</summary>
<p>

```python
handKeypoints = np.array(op.Datum().handKeypoints)[handID, self.personID]

lengthFingers = [np.sqrt((handKeypoints[0,0] - handKeypoints[i,0])**2 + (handKeypoints[0,1] - handKeypoints[i,1])**2) for i in [1,5,9,13,17]] #Initialized with the length of the first segment of each fingers.
for i in range(3): #Add length of other segments for each fingers
    for j in range(len(lengthFingers)):
        lengthFingers[j] += np.sqrt((handKeypoints[1+j*4+i+1, 0] - handKeypoints[1+j*4+i, 0])**2 + (handKeypoints[1+j*4+i+1, 1] - handKeypoints[1+j*4+i, 1])**2)
normMax = max(lengthFingers)

handCenterX = handKeypoints.T[0].sum() / handKeypoints.shape[0]
handCenterY = handKeypoints.T[1].sum() / handKeypoints.shape[0]
outputArray = np.array([(handKeypoints.T[0] - handCenterX)/normMax,
                        -(handKeypoints.T[1] - handCenterY)/normMax,
                        (handKeypoints.T[2])])
```
</p>
</details>

Now that coordinates are normalized, the input data is flatten to be fed to the neural networks as a list of 42 values between -1.0 and 1.0:   <img src="https://render.githubusercontent.com/render/math?math=(k^x_0, k^y_0, k^x_1, k^y_1, \dots   , k^x_{20}, k^y_{20})">

<img src="/.github/markdown/formated_hand.png" width="400">

### 3. Dataset creation - [*9809 samples for 24 output categories*](https://github.com/ArthurFDLR/Robotics_Vision_Simulator/tree/master/AppHandClassifier/Datasets)


## Simulated world

![Hand data Formatting](/.github/markdown/handDataFormatting.png)

![RSV Gui](/.github/markdown/GUIexample.PNG)

![OpenPose test on generated image](/.github/markdown/InSimTest_OpenPose.jpg)
