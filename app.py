from flask import Flask,render_template,request,url_for,redirect,session,send_file,flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import PIL
import numpy as np
from math import ceil, floor
from skimage.io import imsave, imread
from skimage import img_as_float
import os
import boto3
from flask_mail import Mail, Message 
from BiCubic import *

# Configuring Boto3 for s3
s3 = boto3.client('s3',
                    aws_access_key_id = "AKIAJJ4XVJFMZDEVCPEQ",
                    aws_secret_access_key = "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")

# s3 Bucket Names
BUCKET_NAME="myimagebucket1"
BUCKET_NAME2 = "myimagebucket2"

# Configuring the app
app = Flask(__name__)
app.config.update(dict(
    DEBUG = True,
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = 'imageoptimisationofficial@gmail.com',
    MAIL_PASSWORD = 'ImageOp@@4',
))

# Configuring app for Mail
mail = Mail(app)
app.secret_key="gicgE9-xyphim-byqqez"

# Configuring the app for database
pp.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False

# Adding Permanent Session to the app
app.permanent_session_lifetime = timedelta(hours=1)

# Initializing database for the app
db=SQLAlchemy()
db.init_app(app)

# Creating class for users
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Primary key 
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)

    def __init__(self,name,password,email):
        self.name = name
        self.password = password
        self.email = email

# Creating class for files
class files(db.Model):
    _id = db.Column("id",db.Integer,primary_key = True)
    user_id = db.Column("user_id",db.Integer)
    filename = db.Column("filename",db.String(100))

    def __init__(self,user_id,filename):
        self.user_id = user_id
        self.filename = filename

# Creating routes

''' (GET Request) home route to check whether a user is logged in or not'''
@app.route('/home')
def home():
    if "user_id" in session:
        return "User logged in", 201
    else:
        return "Use not logged in", 400


''' (GET Request) Images route to fetch the url to display image thumbnails '''
@app.route("/Images")
def images():
    if "user_id" in session:
        filename = []
        img_paths = []
        user_file = files.query.filter_by(user_id = session["user_id"]).all()
        for i in user_file:
            filename.append(i.filename)
        for name in filename:
            cur = "https://myimagebucket2.s3.us-east-2.amazonaws.com/" + name
            img_paths.append(cur)
        return jsonify({'image':img_paths}), 201
    else:
        return "Please Login",400


''' (GET Request) Login route to check whether the user in session and Logout the user 
(POST Request) Login route to check whether the credentials entered by user are correct or not '''
@app.route('/Login',methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user_data = request.get_json()
        email = user_data["email"]
        password = user_data["password"]
        found_user = User.query.filter_by(email=email).first()
        if not found_user or not check_password_hash(found_user.password, password):
            return "User Not found", 400
        session.permanent = True
        if "user_mail" in session:
            session.pop("user_mail", None)
            session.pop("user_id", None)
        session["user_mail"] = email
        session["user_id"]=found_user.id
        return "Login Successful", 201
    else:
        if "user_mail" in session:
            session.pop("user_mail",None)
            session.pop("user_id",None)
            flash("You have been logged out!","info")
            return "Logged Out", 203
        else:
            return "None Logged in", 201

''' (POST Request) register route to obtain the details of user from registration page and store them in database and send confirmation email to the user's email ''' 
@app.route('/register',methods=['POST'])
def register():
    if request.method == 'POST':
        user_data = request.get_json()
        username = user_data["name"]
        password = generate_password_hash(user_data["password"],method='sha256')
        email = user_data["email"]
        found_user = User.query.filter_by(email=email).first()
        if found_user:
            return "You Already Have an account!!", 400
        new_user = User(name = username,password=password, email=email)
        db.session.add(new_user)
        db.session.commit()
        found_user = User.query.filter_by(email=email).first()
        if "user_mail" in session:
            session.pop("user_mail", None)
            session.pop("user_id", None)
        session["user_mail"] = email
        session["user_id"] = found_user.id
        msg = Message( 
                'Confirmation of Registration on Image Optimisation App', 
                sender ='imageoptimisationofficial@gmail.com', 
                recipients = [email] 
               ) 
        msg.body = 'Welcome to the Image Optimisation Web App, thank you for registering. Enjoy our services. If you did not register in the image optimisation web app, please contact our customer service'
        mail.send(msg)
        return "Done", 201


''' (POST Request) Forgot route to send email to a user to change his password ''' 
@app.route("/Forgot", methods=["POST"])
def forgot():
    data = request.get_json()
    email = data["email"]
    found_user = User.query.filter_by(email=email).first()
    if not found_user:
        return "No user found", 400
    msg = Message( 
                'Image Optimisation Password', 
                sender ='imageoptimisationofficial@gmail.com', 
                recipients = [email] 
               ) 
    msg.body = "Click this link to change your password : www.imageoptimisation.com/change-password"
    mail.send(msg)
    return "Email Sent", 201


''' (POST Request) Upload route to fetch the image from the user and upload it to the s3 database. 
A thumbnail of the image is also uploaded to another bucket in the s3 database to 
dislpay it to the user ''' 
@app.route("/Upload",methods=["POST"])
def upload():
    f = request.files["file"]
    filename = f.filename
    f.save(filename)    
    cur_img = PIL.Image.open(filename)
    MAX_SIZE = (200, 200)
    cur_img.thumbnail(MAX_SIZE, resample=PIL.Image.BILINEAR)
    cur_img.save("thumbnails/" + filename)
    s3.upload_file(Bucket = BUCKET_NAME,Filename = filename,Key = filename)
    s3.upload_file(Bucket = BUCKET_NAME2,Filename = "thumbnails/" + filename,Key = filename)
    user_id = session["user_id"]
    filesaved=files(user_id,filename)
    db.session.add(filesaved)
    db.session.commit()
    user_file = files.query.filter_by(user_id = session["user_id"]).all()
    theobjects = s3.list_objects_v2(Bucket = BUCKET_NAME)
    os.remove(filename)
    os.remove("thumbnails/" + filename)
    #print("https://myimagebucket2.s3.us-east-2.amazonaws.com/" + filename)
    return ("https://myimagebucket2.s3.us-east-2.amazonaws.com/" + filename), 201


''' (POST Request) Resize route to fetch an image from user that he/she wants to resize.
It is uploaded in the s3 database temporarily and is later deleted. '''
@app.route("/Resize", methods=["POST"])
def resize():
    f = request.files["file"]
    filename = f.filename
    f.save(filename)
    s3.upload_file(Bucket = BUCKET_NAME2,Filename = filename,Key = filename)
    return ("https://myimagebucket2.s3.us-east-2.amazonaws.com/" + filename), 201


''' (POST Request) Saveresize route to fetch the new height and width of the image and resize the image
to the new size usign Bicubic Interpolation '''
@app.route("/Saveresize",methods=["POST"])
def saveresize():
    data = request.get_json()
    x = data["x"]
    y = data["y"]
    filepath = data["filepath"]
    filename = filepath.partition(".com/")[2]
    s3.download_file(BUCKET_NAME,filename, filename)
    im_full_size = imread(filename)
    new_width = round(im_full_size.shape[1] * y)
    new_height = round(im_full_size.shape[0] * x)
    im_new = imresize(im_full_size, output_shape=(new_width, new_height))
    os.remove(filename)
    imsave(filename, im_new)
    s3.delete_object(Bucket=BUCKET_NAME2, Key=filename)
    cur_img = PIL.Image.open(filename)
    MAX_SIZE = (200, 200)
    cur_img.thumbnail(MAX_SIZE, resample=PIL.Image.BILINEAR)
    cur_img.save("thumbnails/" + filename)
    s3.upload_file(Bucket = BUCKET_NAME2,Filename = "thumbnails/" + filename,Key = filename)
    s3.upload_file(Bucket = BUCKET_NAME,Filename = filename,Key = filename)
    os.remove(filename)
    os.remove("thumbnails/" + filename)
    return "Done", 201


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True)
    
