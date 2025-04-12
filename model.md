1. Import Libraries
OpenCV (cv2): Used for face detection (Haar Cascade) and image processing (resizing, displaying video frames).

NumPy (np): Used for array manipulations and mathematical operations (cosine similarity, loading/saving embeddings).

os: Used to handle file paths and directories.

tflite_runtime.interpreter (or tensorflow.lite): Handles the TensorFlow Lite interpreter to run the model on the device. This part is conditional based on whether tflite_runtime is available or TensorFlow is used directly.

2. Setup:
Model Path: The path to the TensorFlow Lite model (facenet.tflite) which will be used for face recognition.

Embeddings Directory: A directory (face_embeddings) where face embeddings will be saved or loaded.

Face Detection Parameters: FACE_DETECTION_SCALE and FACE_DETECTION_MIN_NEIGHBORS are parameters for detecting faces using the Haar Cascade classifier.

Matching Threshold: This is the cosine similarity threshold (0.7) above which faces are considered a match.

3. Face Detection Setup:
Haar Cascade Classifier: OpenCV’s pre-trained face detector (haarcascade_frontalface_default.xml) is used to detect faces in the video stream.

4. TensorFlow Lite Model Setup:
TensorFlow Lite Interpreter: The tflite.Interpreter is used to load and allocate the face recognition model (facenet.tflite). The model is optimized for running on mobile and embedded devices like the Raspberry Pi.

Model Input and Output: The input and output details are fetched from the interpreter to ensure data is passed correctly for processing.

5. Embeddings Handling:
Load Embeddings: The function load_embeddings() reads previously saved face embeddings from .npy files in the face_embeddings directory. These embeddings represent unique features of known faces.

Save Embedding: The function save_embedding() saves the embedding for a recognized face to a .npy file. It sanitizes the name to remove non-alphanumeric characters, ensuring valid file names.

6. Face Processing Functions:
Preprocess Face: The function preprocess_face() resizes the detected face to 160x160 pixels and normalizes it to a range of [-1, 1], which is required for input to the model.

Get Embedding: The function get_embedding() takes the preprocessed face and passes it through the TensorFlow Lite model to obtain the embedding (a vector that represents the unique features of the face).

Cosine Similarity: The cosine_similarity() function compares the embedding of the current face with the saved embeddings to measure how similar they are. If the cosine similarity is above the matching threshold (0.7), the faces are considered to match.

7. Main Loop (Video Capture & Face Recognition):
Video Capture: The video feed from the camera is captured using cv2.VideoCapture(0), and each frame is processed to detect faces.

Face Detection: In each frame, the face_cascade.detectMultiScale() function detects faces using Haar Cascade. The function returns the coordinates (x, y, w, h) of each detected face, which are then used to crop the face region from the frame.

Face Recognition: For each detected face, the system preprocesses it, extracts the embedding using the TFLite model, and compares it with saved embeddings using cosine similarity:

Known Faces: If a match is found (similarity > threshold), the system labels the face with the name and similarity score.

Unknown Faces: If no match is found, the system labels the face as "Unknown".

Save New Face: If the user presses 's', the system enters "save mode", where the user is prompted to enter the name of the person. The system then saves the embedding of the detected face for future recognition.

Display: The processed frame with face bounding boxes, names, and similarity scores is displayed in a window. The user can exit the program by pressing 'q'.

8. Keyboard Controls:
q: Quits the program and closes the video stream.

s: Enters save mode, allowing the user to save new face embeddings with an associated name.

-----------------------------------------------------------------------------------------------------------------------------

Face Detection and Recognition:

MTCNN (Face Detection): This model is used to detect faces in the captured frames. It works in three stages, refining the face detection as it progresses. The model can handle faces with different orientations and sizes.

InceptionResnetV1 (Face Recognition): After detecting a face, it is passed through a pre-trained model (InceptionResnetV1) to generate a unique embedding (a vector representation). These embeddings are used to identify or verify faces by comparing them to stored embeddings of known individuals.

Motion Detection:

The system uses a simple method to detect motion by comparing consecutive frames of the video. If significant differences are detected between frames (indicating motion), the system triggers the face recognition process.

Embedding Storage:

The system maintains a directory of saved face embeddings (face_embeddings). Each embedding corresponds to a known individual. The embeddings are precomputed and stored in .npy files for efficient comparison.

Recognition Logic:

When motion is detected, faces are identified in the frame. The system compares the embeddings of these detected faces with the stored embeddings.

If a known face is detected (i.e., the cosine similarity of embeddings is below a threshold), the system outputs the name of the individual and terminates further processing.

If an unknown face is detected (i.e., no match is found), the system outputs 0.

Threading:

A separate thread is used for face recognition to ensure real-time video capture and processing. The main video capture loop captures frames continuously and passes them to the recognition thread for face detection and identification.

Output & Termination:

If a known face is recognized, the system prints the name of the individual and stops further processing. If an unknown face is detected, the system prints 0.

The system terminates when a known face is detected, and it stops the recognition thread.

Process Flow:
Video Capture: The camera feed is continuously captured.

Motion Detection: Each frame is compared with the previous frame to check for motion.

Face Detection and Recognition: If motion is detected, the system looks for faces and compares each one to the known embeddings.

Output: If a known face is detected, it outputs the name and stops. If no known face is found, it outputs 0.

Real-Time Performance:
The use of threading and frame skipping allows the system to handle real-time processing efficiently without overwhelming the hardware. It only processes frames when necessary (i.e., when motion is detected) to reduce the computational load.

Logging:
All significant events, such as starting the system or detecting faces, are logged into a file (intruder_detection.log) for troubleshooting and auditing.