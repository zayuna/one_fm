import frappe
from frappe import _
from frappe.utils import now_datetime, cstr, nowdate
from scipy.spatial import distance as dist
from imutils.video import FileVideoStream
from imutils.video import VideoStream
from imutils import face_utils, paths
import numpy as np
import face_recognition
import imutils
import time
import dlib
import pickle, cv2, os
from itertools import repeat
import multiprocessing as mp
from time import perf_counter
from multiprocessing import Pool



def eye_aspect_ratio(eye):
	# compute the euclidean distances between the two sets of
	# vertical eye landmarks (x, y)-coordinates
	A = dist.euclidean(eye[1], eye[5])
	B = dist.euclidean(eye[2], eye[4])
	# compute the euclidean distance between the horizontal
	# eye landmark (x, y)-coordinates
	C = dist.euclidean(eye[0], eye[3])
	# compute the eye aspect ratio
	ear = (A + B) / (2.0 * C)
	# return the eye aspect ratio
	return ear


def setup_directories():
	"""
		Use this function to create directories needed for the face recognition system: dataset directory and facial embeddings
	"""
	from pathlib import Path
	Path(frappe.utils.cstr(frappe.local.site)+"/private/files/user/").mkdir(parents=True, exist_ok=True)
	Path(frappe.utils.cstr(frappe.local.site)+"/private/files/dataset/").mkdir(parents=True, exist_ok=True)
	Path(frappe.utils.cstr(frappe.local.site)+"/private/files/facial_recognition/").mkdir(parents=True, exist_ok=True)
	Path(frappe.utils.cstr(frappe.local.site)+"/private/files/face_rec_temp/").mkdir(parents=True, exist_ok=True)
	Path(frappe.utils.cstr(frappe.local.site)+"/private/files/dataset/"+frappe.session.user+"/").mkdir(parents=True, exist_ok=True)

@frappe.whitelist()
def enroll():
	try:
		setup_directories()
		files = frappe.request.files
		file = files['file']
		content = file.stream.read()
		filename = file.filename	
		OUTPUT_VIDEO_PATH = frappe.utils.cstr(frappe.local.site)+"/private/files/user/"+filename
		with open(OUTPUT_VIDEO_PATH, "wb") as fh:
				fh.write(content)
				create_dataset(OUTPUT_VIDEO_PATH)
		return _("Successfully Enrolled!")
	except Exception as exc:
		frappe.log_error(frappe.get_traceback())
		raise exc


@frappe.whitelist()
def verify():
	try:
		setup_directories()
		log_type = frappe.local.form_dict['log_type']
		skip_attendance = frappe.local.form_dict['skip_attendance']
		latitude = frappe.local.form_dict['latitude']
		longitude = frappe.local.form_dict['longitude']
		timestamp = frappe.local.form_dict['timestamp']

		files = frappe.request.files
		file = files['file']
		content = file.stream.read()
		filename = file.filename	
		OUTPUT_IMAGE_PATH = frappe.utils.cstr(frappe.local.site)+"/private/files/user/"+filename

		with open(OUTPUT_IMAGE_PATH, "wb") as fh:
				fh.write(content)
				blinks, image = verify_face(OUTPUT_IMAGE_PATH)
				if blinks > 0:
					if recognize_face(image):
						return check_in(log_type, skip_attendance, latitude, longitude, timestamp)
					else:
						frappe.throw(_('Face Recognition Failed. Please try again.'))	
				else:
					frappe.throw(_('Liveness Detection Failed. Please try again.'))
	except Exception as exc:
		frappe.log_error(frappe.get_traceback())
		raise exc


def check_in(log_type, skip_attendance, latitude, longitude, timestamp):
	employee = frappe.get_value("Employee", {"user_id": frappe.session.user})
	checkin = frappe.new_doc("Employee Checkin")
	checkin.employee = employee
	checkin.log_type = log_type
	checkin.device_id = cstr(latitude)+","+cstr(longitude)
	check_in.skip_auto_attendance = skip_attendance
	checkin.time = now_datetime()
	checkin.actual_time = now_datetime()
	checkin.save()
	frappe.db.commit()
	return _('Check {log_type} successful! {docname}'.format(log_type=log_type.lower(), docname=checkin.name))


def create_dataset(video):
	OUTPUT_DIRECTORY = frappe.utils.cstr(frappe.local.site)+"/private/files/dataset/"+frappe.session.user+"/"
	# vs = FileVideoStream(video).start()
	# fileStream = True
	count = 0 
	# while True:
	# 	# if this is a file video stream, then we need to check if
	# 	# there any more frames left in the buffer to process
	# 	if fileStream and not vs.more():
	# 		break
		
	# 	if not isinstance(vs.read(), np.ndarray):
	# 		break

	# 	if vs.read() is None:
	# 		break
	# 	# grab the frame from the threaded video file stream, resize
	# 	# it, and convert it to grayscale
	# 	# channels)
	# 	frame = vs.read()
	# 	print(frame)
	# 	cv2.imwrite(OUTPUT_DIRECTORY + "{0}.jpg".format(count+1), frame)
	# 	count = count + 1
	
	cap = cv2.VideoCapture(video)
	success, img = cap.read()
	# fno = 0
	while success:
		cv2.imwrite(OUTPUT_DIRECTORY + "{0}.jpg".format(count+1), img)
		count = count + 1
		# read next frame
		success, img = cap.read()

	create_encodings(OUTPUT_DIRECTORY)
	doc = frappe.get_doc("Employee", {"user_id": frappe.session.user})
	print(doc.as_dict())
	doc.enrolled = 1
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	# print("execution_time", os.cpu_count())
	# print("execution_time", OUTPUT_DIRECTORY)
	# imagePaths = list(paths.list_images(OUTPUT_DIRECTORY))

	# create_encodings(imagePaths)
	# try:
	# 	start = perf_counter()
	# 	# pool = Pool(os.cpu_count() - 1) # max cpus - 1
	# 	OUTPUT_ENCODING_PATH_PREFIX = frappe.utils.cstr(frappe.local.site)+"/private/files/facial_recognition/"
	# 	user_id = frappe.session.user
	# 	#encodings file output path
	# 	encoding_path = OUTPUT_ENCODING_PATH_PREFIX + user_id +".pickle"
	# 	with mp.Manager() as manager:
	# 		data = manager.dict(encodings=[])
	# 		with manager.Pool() as pool:
	# 			pool.starmap(create_encodings,zip(imagePaths, repeat(data), repeat(OUTPUT_ENCODING_PATH_PREFIX), repeat(user_id),repeat(encoding_path)))
			
	# 		print(data)
	# 		f = open(encoding_path, "wb")
	# 		f.write(pickle.dumps(dict(data)))
	# 		f.close()
	# 	# data = {}
	# 	# pool.starmap(create_encodings,[imagePaths, data])
		
	# 	end = perf_counter()
	# 	execution_time = (end - start)
	# 	print(execution_time)
	# 	doc = frappe.get_doc("Employee", {"user_id": frappe.session.user})
	# 	print(doc.as_dict())
	# 	doc.enrolled = 1
	# 	doc.save(ignore_permissions=True)
	# 	frappe.db.commit()
	# finally: # To make sure processes are closed in the end, even if errors happen
	# 	# pool.close()
	# 	# pool.join()
	# 	pass


# def create_encodings(imagePaths, data, OUTPUT_ENCODING_PATH_PREFIX, user_id, encoding_path, detection_method="hog"):# detection_method can be "hog" or "cnn". cnn is more cpu and memory intensive.
# 	"""
# 		directory : directory path containing dataset 
# 	"""
# 	# grab the paths to the input images in our dataset


# 	# initialize the list of known encodings and known names
# 	knownEncodings = []
# 	knownNames = []

# 	# extract the person name from the image path i.e User Id
# 	# print("[INFO] processing image {}/{}".format(i + 1, len(imagePaths)))
# 	name = imagePaths.split(os.path.sep)[-2]

# 	# load the input image and convert it from BGR (OpenCV ordering)
# 	# to dlib ordering (RGB)
# 	image = cv2.imread(imagePaths)
# 	rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 	# detect the (x, y)-coordinates of the bounding boxes
# 	# corresponding to each face in the input image
# 	boxes = face_recognition.face_locations(rgb, model=detection_method)

# 	# compute the facial embedding for the face
# 	encodings = face_recognition.face_encodings(rgb, boxes)
# 	len(encodings) > 0 and data["encodings"].append(encodings[0])
# 	# knownEncodings.append(encodings[0])

# 	# dump the facial encodings + names to disk	
# 	# data["encodings"].append(knownEncodings)

def create_encodings(directory, detection_method="hog"):# detection_method can be "hog" or "cnn". cnn is more cpu and memory intensive.
	"""
		directory : directory path containing dataset 
	"""
	print(directory)
	OUTPUT_ENCODING_PATH_PREFIX = frappe.utils.cstr(frappe.local.site)+"/private/files/facial_recognition/"
	user_id = frappe.session.user
	# grab the paths to the input images in our dataset
	imagePaths = list(paths.list_images(directory))
	print(imagePaths)
	#encodings file output path
	encoding_path = OUTPUT_ENCODING_PATH_PREFIX + user_id +".pickle"
	# initialize the list of known encodings and known names
	knownEncodings = []
	# knownNames = []

	for (i, imagePath) in enumerate(imagePaths):
		# extract the person name from the image path i.e User Id
		print("[INFO] processing image {}/{}".format(i + 1, len(imagePaths)))
		name = imagePath.split(os.path.sep)[-2]

		# load the input image and convert it from BGR (OpenCV ordering)
		# to dlib ordering (RGB)
		image = cv2.imread(imagePath)
		rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

		# detect the (x, y)-coordinates of the bounding boxes
		# corresponding to each face in the input image
		boxes = face_recognition.face_locations(rgb, model=detection_method)

		# compute the facial embedding for the face
		encodings = face_recognition.face_encodings(rgb, boxes)

		# loop over the encodings
		for encoding in encodings:
			# add each encoding + name to our set of known names and
			# encodings
			knownEncodings.append(encoding)

	# dump the facial encodings + names to disk	
	data = {"encodings": knownEncodings}
	print(data)
	f = open(encoding_path, "wb")
	f.write(pickle.dumps(data))
	f.close()



def verify_face(video_path=None):
	# video_path = frappe.utils.cstr(frappe.local.site)+"/private/files/kartik2.mp4"
	shape_predictor = frappe.utils.cstr(frappe.local.site)+"/private/files/shape_predictor_68_face_landmarks.dat"
	# define two constants, one for the eye aspect ratio to indicate
	# blink and then a second constant for the number of consecutive
	# frames the eye must be below the threshold
	EYE_AR_THRESH = 0.3
	EYE_AR_CONSEC_FRAMES = 2
	# initialize the frame counters and the total number of blinks
	COUNTER = 0
	TOTAL = 0

	# initialize dlib's face detector (HOG-based) and then create
	# the facial landmark predictor
	print("[INFO] loading facial landmark predictor...")
	detector = dlib.get_frontal_face_detector()
	predictor = dlib.shape_predictor(shape_predictor)

	# grab the indexes of the facial landmarks for the left and
	# right eye, respectively
	(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
	(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

	# start the video stream thread
	print("[INFO] starting video stream thread...")
	vs = FileVideoStream(video_path).start()
	fileStream = True
	# vs = VideoStream(src=0).start()
	# vs = VideoStream(usePiCamera=True).start()
	# fileStream = False
	time.sleep(1.0)
	# print(vs.read())	
	# loop over frames from the video stream
	IMAGE_PATH = ""

	while True:
		# if this is a file video stream, then we need to check if
		# there any more frames left in the buffer to process
		if fileStream and not vs.more():
			break
		
		if not isinstance(vs.read(), np.ndarray):
			break

		if vs.read() is None:
			break
		# grab the frame from the threaded video file stream, resize
		# it, and convert it to grayscale
		# channels)
		frame = vs.read()

		frame = imutils.resize(frame, width=640)
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

		# detect faces in the grayscale frame
		rects = detector(gray, 0)

		# loop over the face detections
		for rect in rects:
			# determine the facial landmarks for the face region, then
			# convert the facial landmark (x, y)-coordinates to a NumPy
			# array
			shape = predictor(gray, rect)
			shape = face_utils.shape_to_np(shape)

			# extract the left and right eye coordinates, then use the
			# coordinates to compute the eye aspect ratio for both eyes
			leftEye = shape[lStart:lEnd]
			rightEye = shape[rStart:rEnd]
			leftEAR = eye_aspect_ratio(leftEye)
			rightEAR = eye_aspect_ratio(rightEye)

			# average the eye aspect ratio together for both eyes
			ear = (leftEAR + rightEAR) / 2.0

			# compute the convex hull for the left and right eye, then
			# visualize each of the eyes
			leftEyeHull = cv2.convexHull(leftEye)
			rightEyeHull = cv2.convexHull(rightEye)
			# cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
			# cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)

			# check to see if the eye aspect ratio is below the blink
			# threshold, and if so, increment the blink frame counter
			print(ear, EYE_AR_THRESH)
			if ear < EYE_AR_THRESH:
				COUNTER += 1
				print("[TOTAL COUNTER]", COUNTER)

			# otherwise, the eye aspect ratio is not below the blink
			# threshold
			else:
				# if the eyes were closed for a sufficient number of
				# then increment the total number of blinks
				if COUNTER >= EYE_AR_CONSEC_FRAMES:
					IMAGE_PATH = frappe.utils.cstr(frappe.local.site)+"/private/files/"+frappe.session.user+".png"
					TOTAL += 1
					print("[TOTAL TOTAL]", TOTAL)
					cv2.imwrite(IMAGE_PATH,frame)
					return TOTAL, IMAGE_PATH

				# reset the eye frame counter
				COUNTER = 0
	
			print( "Blinks: {}".format(TOTAL), "EAR: {:.2f}".format(ear))

	print("[TOTAL]", TOTAL)
	print("[COUNT]", COUNTER)
	
	# do a bit of cleanup
	# cv2.destroyAllWindows()
	vs.stop()
	return TOTAL, IMAGE_PATH


def recognize_face(image):
	try:
		print(image)
		ENCODINGS_PATH = frappe.utils.cstr(
			frappe.local.site)+"/private/files/facial_recognition/"+frappe.session.user+".pickle"
		# values should be "hog" or "cnn" . cnn is CPU and memory intensive.
		DETECTION_METHOD = "hog"
		print(ENCODINGS_PATH)

		# load the known faces and embeddings
		face_data = pickle.loads(open(ENCODINGS_PATH, "rb").read())

		# load the input image and convert it from BGR to RGB
		image = cv2.imread(image)
		rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

		# detect the (x, y)-coordinates of the bounding boxes corresponding
		# to each face in the input image, then compute the facial embeddings
		# for each face
		boxes = face_recognition.face_locations(rgb,
												model=DETECTION_METHOD)
		encodings = face_recognition.face_encodings(rgb, boxes)
		print(encodings)

		if not encodings:
			return False
		return match_encodings(encodings, face_data)

	except Exception as e:
		print(frappe.get_traceback())


def match_encodings(encodings, face_data):
	try:
		# loop over the facial embeddings
		for encoding in encodings:
			# attempt to match each face in the input image to our known
			# encodings
			matches = face_recognition.compare_faces(
				face_data["encodings"], encoding)
			# check to see if we have found a match
			if True in matches:
				# find the indexes of all matched faces
				matchedIdxs = [i for (i, b) in enumerate(matches) if b]
				print(matchedIdxs, matches)
				return True if ((len(matchedIdxs) / len(matches)) * 100 > 80) else False
			else:
				return False
		else:
			return False
	except Exception as identifier:
		print(frappe.get_traceback())


@frappe.whitelist()
def check_existing():
	employee = frappe.get_value("Employee", {"user_id": frappe.session.user})
	if not employee:
		frappe.throw(_("Please link an employee to the logged in user to proceed further."))
	
	logs = frappe.db.sql("""
		select name, log_type from `tabEmployee Checkin` where date(time)=date("{date}") and skip_auto_attendance=0 and employee="{employee}" 
	""".format(date=nowdate(), employee=employee), as_dict=1)
	print(logs)
	val = [log.log_type for log in logs]
	print(not val)
	print(len(val) == 0)
	print(val and "OUT" in val)
	if not val or (val and "OUT" in val):
		return False	
	else:
		return True