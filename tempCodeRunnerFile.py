from flask import Flask, render_template, request, redirect ,url_for
import requests
from werkzeug.utils import secure_filename
import uuid
import os
import ast
import re
from apscheduler.schedulers.background import BackgroundScheduler
from htmlbody import *
import uuid
from firebase import firebase_admin
from firebase_admin import auth

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from datetime import *
import smtplib
from firebase import firebase_ref

app = Flask(__name__)

app.config['token'] = ""
app.config['email'] = ""
app.config['UPLOAD_FOLDER_SCAN'] = r"C:\Users\morya\Desktop\study\Projecty\scanPlus-main\frontend\static\temp"
upload_folder_prescriptions = r"C:\Users\morya\Desktop\study\Projecty\scanPlus-main\api\images\prescriptions"
app.config["UPLOAD_FOLDER_prescriptions"] = upload_folder_prescriptions


scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
# scheduler.__init__(app)
scheduler.start()

api_url = "http://127.0.0.1:5000"

from flask_mail import Mail, Message

app.config.update(dict(
    MAIL_DEBUG = True,
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = "wateruknown7@gmail.com",
    MAIL_PASSWORD = "monish@2004"
))

mail= Mail(app)

def send_mail(message, mail_id):
    with app.app_context():
        msg = Message('Hello', sender = "waterunknow7@gmail.com", recipients = [mail_id])
        # mail.send(msg)
        msg.html = mail_body(message)
        mail.send(msg)
        print("Sent")
        return


@app.route("/", methods = ["GET"])
def home_page():
    return render_template("home.html")

@app.route("/about", methods = ["GET"])
def about():
    return render_template("about.html")

@app.route("/contact", methods = ["GET"])
def contact():
    return render_template("contact.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if request.method == "GET":
        if not app.config['token']:
            return redirect(url_for('scan'))  # Redirect to login if not authenticated

        url = "http://127.0.0.1:5000/dashboard"
        headers = {
            'Authorization': 'Bearer ' + app.config['token']
        }

        response = requests.request("GET", url, headers=headers)

        if response.status_code == 200:
            data = ast.literal_eval(response.text)
            name = data.get('name', 'Unknown')
            return render_template("dashboard.html", name=name)
        else:
            return "Invalid Token"
    else:
        # Handle POST request if needed
        pass




@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        dob = request.form['dob']
        gender = request.form['gender']
        location = request.form['location']

        # Store user data in Firebase
        new_user = {
            'name': name,
            'email': email,
            'password': password,  # Note: You should NOT store passwords in plaintext in a real app
            'dob': dob,
            'gender': gender,
            'location': location
        }
        firebase_ref.push(new_user)

        # Redirect to dashboard after successful signup
        return redirect(url_for('dashboard'))

    else:
        # Handle GET request if needed
        return render_template('signup.html')
    
@app.route("/login", methods = ["POST", "GET"])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        try:
            # Get the user by email
            users = firebase_ref.order_by_child('email').equal_to(email).get()

            if users:
                # Since email should be unique, there should be only one user
                user_key = list(users.keys())[0]
                user_data = users[user_key]

                # Check if the provided password matches the stored password
                if user_data['password'] == password:
                    # Passwords match, redirect to dashboard
                    user_name = user_data['name']  # Get the user's name
                    return render_template("dashboard.html", user_name=user_name)
                else:
                    # Passwords don't match, redirect to login with status=invalid
                    return redirect("/login?status=invalid")
            else:
                # User not found, redirect to login with status=invalid
                return redirect("/login?status=invalid")

        except Exception as e:
            # Handle any other exceptions
            print(str(e))
            return redirect("/login?status=error")

    else:
        status = request.args.get('status')
        return render_template("login.html", status=status)

    
@app.route("/scan", methods = ["GET", "POST"])
def scan():
    if request.method == "POST":
        # Get the uploaded file
        pic = request.files['picture']

        # Generate a unique filename for the uploaded image
        pic_filename = secure_filename(pic.filename)
        pic_name = str(uuid.uuid1()) + "_" + pic_filename

        # Ensure the directory exists before saving the file
        upload_folder_scan = app.config['UPLOAD_FOLDER_SCAN']
        if not os.path.exists(upload_folder_scan):
            os.makedirs(upload_folder_scan)

        # Save the uploaded image to the specified directory
        pic.save(os.path.join(upload_folder_scan, pic_name))

        # Prepare data for the scan API
        data = {'path': os.path.join(upload_folder_scan, pic_name)}

        # Make a request to the scan API
        response = requests.post(api_url + '/scan', data).json()
        response = ast.literal_eval(response)

        # Process the response to extract medicine and frequency information
        medicines_list = [(medicine[0], frequency[0]) for medicine, frequency in zip(response.get('Medicine', []), response.get('Frequency', []))]

        # Extract email from the form data
        email = request.form.get('email', '')

        # Prepare a list of tuples with medicine and days
        working_list = [(medicine[0], int(re.findall(r'\d+', frequency[0])[0])) for medicine, frequency in zip(response.get('Medicine', []), response.get('Frequency', []))]

        # Schedule email sending jobs for each medicine
        for medicine, days in working_list:
            end_date = datetime.now() + timedelta(days=days)
            job_date = max(datetime.now(), end_date - timedelta(days=1))  # Ensure the initial job runs at least once
            scheduler.add_job(send_mail, 'interval', [medicine, email], days=1, end_date=end_date, next_run_time=job_date)

        # Extract name from the response
        name = response.get('Name', [''])[0]

        # Render the template with the relevant information
        return render_template("scan_result.html", name=name, medicine=medicines_list, output=response, pic=pic_name)
    else:
        # Render the scan template for GET requests
        return render_template("scan.html")
    


        
@app.route("/dashboard/upload", methods=["POST"])
def dashboard_upload():
    
    if request.method == "POST":
        
        # Get the uploaded image
        image = request.files['prescription']

        # Generate a unique filename for the uploaded image
        pic_filename = secure_filename(image.filename)
        pic_name = str(uuid.uuid1()) + "_" + pic_filename

        # Save the uploaded image to the specified directory
        upload_folder_prescriptions = app.config['UPLOAD_FOLDER_prescriptions']
        image.save(os.path.join(upload_folder_prescriptions, pic_name))

        # Prepare data for the API
        data = {
            'pic_name': pic_name,
            'email': app.config['email']  # Make sure this is set somewhere in your app
        }

        url = "http://127.0.0.1:5000/dashboard/upload_prescription"
        headers = {
            'Authorization': 'Bearer ' + app.config['token']
        }

        response = requests.post(url, data=data, headers=headers)

        if response.status_code == 200:
            # Prescription upload successful
            return "Prescription uploaded successfully."
        else:
            # Handle any errors
            return "Error uploading prescription."

    else:
        # Render the scan template for GET requests
        return render_template("scan.html")



if __name__=="__main__":
    app.run(debug=True, port=8000)