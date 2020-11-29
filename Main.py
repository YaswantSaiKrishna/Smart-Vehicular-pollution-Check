# Import Dependencies
from azure.cognitiveservices.vision.customvision.training import CustomVisionTrainingClient
from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient
from azure.cognitiveservices.vision.customvision.training.models import ImageFileCreateBatch, ImageFileCreateEntry, Region
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, __version__
from msrest.authentication import ApiKeyCredentials
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from datetime import date 
from picamera import PiCamera
from time import sleep
import datetime
import numpy as np
import requests
import imutils
import json
import time
import cv2
import random
import os, uuid
from mq import *

# Custom Computer Vision model endpoint and prediction key
ENDPOINT = "<Custom vision model endpoint>"
prediction_key = "<Prediction Key of custom vision model>"

# Define Read API OCR endpoint and Read API OCR key
read_api_url = "<Read API OCR endpoint>"
read_api_key = "ReadAPIKey"

camera.start_preview()
sleep(5)
camera.capture('/home/pi/Desktop/image.jpg')
camera.stop_preview()

#Define target image
target_image_path = "/home/pi/Desktop/image.jpg"

# Load an color (1) image in grayscale (0)
img = cv2.imread(target_image_path, 1)

# Convert image to byte string
img_str = cv2.imencode(".jpg", img)[1].tostring()

# Perform object detection using the custom vision service
custom_vision_response = requests.post(
    url=ENDPOINT, 
    data=img_str, 
    headers={
    "Content-Type": "application/octet-stream",
    "Prediction-Key": prediction_key,
    }
).json()


# Find bounding box with the highest confidence level
best_custom_vision_prediction = max(
    custom_vision_response["predictions"], key=lambda x: x["probability"]
)

# Extract the bounding box
bounding_box = best_custom_vision_prediction["boundingBox"]

# Define vertical distance from the left border
x = np.int32(bounding_box["left"] * img.shape[1])

# Define horizontal distance from the top border
y = np.int32(bounding_box["top"] * img.shape[0])

# Define rectangle width
w = np.int32(bounding_box["width"] * img.shape[1])

# Define rectangle height
h = np.int32(bounding_box["height"] * img.shape[0])

# Define top left point
point_one = (x, y)

# Define bottom right point
point_two = (x + w, y + h)

# Plot bounding box on image
img_box = cv2.rectangle(img, point_one, point_two, color=(0, 255, 0), thickness=2)

# Display image
plt.imshow(img_box)
plt.show()


# Crop image
img_crop = img[point_one[1] : point_two[1], point_one[0] : point_two[0]]

# Resize image if width less than 500 pixels
if img_crop.shape[1] < 500:
    img_resize = imutils.resize(img_crop, width=500)

# Display cropped image
plt.imshow(img_resize)
plt.show()


# Convert cropped image to byte string
img_str = cv2.imencode(".jpg", img_resize)[1].tostring()

# Call Read API to perform OCR
response = requests.post(
    url=read_api_url,
    data=img_str,
    headers={
        "Ocp-Apim-Subscription-Key": read_api_key,
        "Content-Type": "application/octet-stream",
    },
)


# Call Read API to get result
response_final = requests.get(
    response.headers["Operation-Location"],
    headers={"Ocp-Apim-Subscription-Key": read_api_key},
)

result = response_final.json()


# Find text identified by the API
text = ""
for line in result["analyzeResult"]["readResults"][0]["lines"]:
    #print("Recognised text:", line["text"])
    text+=line["text"]
    
    
if len(text)==10:
  pass
elif len(text)>10:
  text=text[-10:]
else:
  pass
print(text)


# Returns the current local date 
today = date.today()
flaglist = ["-1"]

# Your storage connection string for use with the application.
connect_str = "DefaultEndpointsProtocol=https;AccountName=numberplatestrg;AccountKey=ASJiNQsDuzXe+DkJo2/hOu6LWl1p98siQsiqDyG3e5iBZKmoEqjlvT3Z/rQ7me/eP6qXHOmgMmrNqD1ccShd8Q==;EndpointSuffix=core.windows.net"

# Create the BlobServiceClient object which will be used to create a container client
blob_service_client = BlobServiceClient.from_connection_string(connect_str)

if flaglist[0] != str(date.today()):
  try:
    flaglist[0] = str(date.today()) 
    # Create a unique name for the container
    container_name = str(date.today())
    # Create the container
    container_client = blob_service_client.create_container(container_name)
  except:
    pass
    
    
# ts store timestamp of current time
ct = datetime.datetime.now()  
ts = ct.timestamp() 

# Create a file in local data directory to upload and download
local_file_name = str(ts) + ".jpg"
upload_file_path = "/home/pi/Desktop/image.jpg"

# Create a blob client using the local file name as the name for the blob
blob_client = blob_service_client.get_blob_client(container=container_name, blob=local_file_name)

print("\nUploading to Azure Storage as blob:\n\t" + local_file_name)

# Upload the created file
with open(upload_file_path, "rb") as data:
    blob_client.upload_blob(data)
    
    
    
table_service = TableService(account_name='<Name of storage account>', account_key='<TableStorage Account Key>')
#table_service.create_table('CarDetails')

#Insert Record
car1 = {'PartitionKey': 'Car', 'RowKey' : '<NumberPlate>',
        'OwnerName' : 'xxxxx', 'ContactNo' : '+91-xxxxx xxxxx', 'PollutionLevel' : 0, 'LastCheckedDate' : '2020-11-15',
        'AmountToBePaid' : 0, 'TimeStamps' : ""}
table_service.insert_entity('CarDetails', car1)

#Query
task = table_service.get_entity('CarDetails', 'Car', str(text))

mq = MQ();
perc = mq.MQPercentage()
poll = perc["CO"]
today = date.today()
l = str(task.LastCheckedDate)
l = date(int(l[0:4]), int(l[5:7]), int(l[8:]))
delta = (today - l)
if poll>500 and delta.days > 10:
  task.PollutionLevel = poll
  task.LastCheckedDate = today
  task.AmountToBePaid = task.AmountToBePaid + 100
  task.TimeStamps = task.TimeStamps + "-" + str(ts)
  #Logic App
  Message = "Hello " + str(task.OwnerName) + ", It is observed that the pollution levels for your vehicle " + str(task.RowKey) + " is above the normal level. Please pay a fine of Rs. " + str(task.AmountToBePaid) + " online or in your nearest RTO office."
  custom_header = {"Content-Type": "application/json"}
  payload = {
    "message": Message,
    "phone": str(task.ContactNo)
    }
  url1 = "https://prod-07.southeastasia.logic.azure.com:443/workflows/9a7427f3044e49779a219b598d56b6fc/triggers/manual/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=2jWGtSi8Uq8RXOxgEq2GDushmXWmgV8XGBhLE7mQwbo"
  response = requests.post(url=url1, headers=custom_header, data=json.dumps(payload))
  
  
