from pdf2image import convert_from_path
import os
import json

# base path of where the images will be hosted
base_host_path = "https://htx-pub.s3.amazonaws.com/demo/pdf"
# path to the folder containing your pdfs
pdf_folder = "./pdfs"
data_json = []

# get all pdfs in the subdir "pdfs" in this directory
for file in os.listdir(pdf_folder):
    name, extension = os.path.splitext(file)
    if extension == ".pdf":
        # if the file is a pdf, convert pdf to images using pdf2image
        images = convert_from_path(f'pdfs/{file}')
        img_list = []
        # save every image and add the urls to a list
        for i, image in enumerate(images):
            file_name = f'{name}_{i}.jpg'
            image.save(file_name, 'JPEG')
            img_list.append(f'{base_host_path}/{file_name}')
        data_json.append({"data": {"pages": img_list}})

with open("data_json.json", 'w') as f:
    json.dump(data_json, f)
