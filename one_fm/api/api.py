import frappe, base64, requests, firebase_admin, json
from frappe import _
import pandas as pd
from frappe.utils import cstr, cint
from frappe.model.rename_doc import rename_doc
from firebase_admin import messaging, credentials
from frappe.desk.page.user_profile.user_profile import get_energy_points_heatmap_data, get_user_rank
from frappe.social.doctype.energy_point_log.energy_point_log import get_energy_points, get_user_energy_and_review_points
import one_fm.api.v1 as v1_api


@frappe.whitelist()
def initialize_firebase():
    """
        Initialize Firebase-Admin
    """
    #fetch credential file to initilize Firebase SDK
    try:
        firebase_admin.get_app()
    except:
        cred = credentials.Certificate(frappe.utils.cstr(frappe.get_site_path())+"/one-fm-70641-b59ee5eae480.json")
        firebase_admin.initialize_app(cred)


@frappe.whitelist()
def _one_fm():
    print(frappe.local.lang)

def set_posts_active():
    posts = frappe.get_all("Operations Post", {"site": "Head Office"})
    for post in posts:
        for date in pd.date_range(start="2021-03-01", end="2021-03-31"):
            sch = frappe.new_doc("Post Schedule")
            sch.post = post.name
            sch.date = cstr(date.date())
            sch.post_status = "Planned"
            sch.save()
    
@frappe.whitelist()
def change_user_profile(image):
    content = base64.b64decode(image)
    filename = frappe.session.user+".png"
    OUTPUT_IMAGE_PATH = frappe.utils.cstr(frappe.local.site)+"/public/files/ProfileImage/"+filename
    fh = open(OUTPUT_IMAGE_PATH, "wb")
    fh.write(content)
    fh.close()
    image_file="/files/ProfileImage/"+filename
    try:
        user = frappe.get_doc("User", frappe.session.user)
        user.user_image = image_file
        user.save()
        frappe.db.commit()
        return {"message": "Success","data_obj": {user},"status_code" : 200}
    except Exception as e:
        print(frappe.get_traceback())
        return {"message": "Some Problem Occured","data_obj": {},"status_code" : 500}

@frappe.whitelist()
def get_user_details():
    try:
        user_id = frappe.session.user
        user= frappe.get_value("User",user_id,"*")
        employee_ID = frappe.get_value("Employee", {"user_id": user_id}, ["name","designation"])
        
        Rank = get_user_rank(user_id)
        energy_Review_Point = get_user_energy_and_review_points(user_id)

        user_details={}
        user_details["Name"]=user.full_name
        user_details["Email"]=user.email
        user_details["Mobile_no"]= user.mobile_no
        user_details["Designation"]= employee_ID[1]
        user_details["EMP_ID"]= employee_ID[0]
        user_details["User_Image"] = user.user_image
        user_details["Monthly_Rank"] = str(Rank["monthly_rank"]).strip('[]') if len(Rank["monthly_rank"])!=0 else "0"
        user_details["Rank"] = str(Rank["all_time_rank"]).strip('[]') if len(Rank["all_time_rank"])!=0 else "0"
        user_details["Energy_Point"] = str(int(energy_Review_Point[user_id]["energy_points"])) if len(energy_Review_Point)!=0 else "0"
        user_details["Review_Point"] = str(int(energy_Review_Point[user_id]["review_points"])) if len(energy_Review_Point)!=0 else "0"
        return user_details
    except Exception as e:
        print(frappe.get_traceback())

@frappe.whitelist()
def upload_file(doc, fieldname, filename, file_url, content, is_private):
    doc = frappe.get_doc({
			"doctype": "File",
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"attached_to_field": fieldname,
			"file_name": filename,
			"file_url": file_url,
			"is_private": cint(is_private),
			"content": content
		})
    doc.save()
    frappe.db.commit()
    return doc

@frappe.whitelist()
def get_user_roles():
    user_id = frappe.session.user
    user_roles = frappe.get_roles(user_id)
    return user_roles

def rename_posts():
    sites = frappe.get_all("Operations Site")
    for site in sites:
        posts = frappe.get_all("Operations Post", {"site": site.name}, ["name", "post_name", "gender", "site_shift"])
        frappe.enqueue(rename_post, posts=posts, is_async=True, queue="long")


def rename_post(posts):
    for post in posts:
        new_name = "{post_name}-{gender}|{site_shift}".format(post_name=post.post_name, gender=post.gender, site_shift=post.site_shift)
        try:
            rename_doc("Operations Post", post.name, new_name, force=True)
        except Exception as e:
            print(frappe.get_traceback())

@frappe.whitelist()
def store_fcm_token(employee_id ,fcm_token,device_os):
    """
    This function stores FCM Token  and Device OS in employee doctype 
    that is fetched from device/app end when user logs in.
    
    Params: Employee ID (Single employee ID), FCM Token and Device OS comes from the client side.
    
    It returns true or false based on the execution.
    """
    Employee = frappe.get_doc("Employee",{"name":employee_id})
    try:
        if Employee:
            Employee.fcm_token = fcm_token
            Employee.device_os = device_os
            Employee.save()
            frappe.db.commit()
            return True
        else:
            return False
    except Exception as e:
        print(frappe.get_traceback())


@frappe.whitelist()
def push_notification_for_checkin(employee_id, title, body, checkin, arriveLate ,checkout):
    """
    This Function send push notification to group of devices. here, we use 'firebase admin' library to send the message.
    
    Params: employee_id is a list of employee ID's,
    title and body are message string to send it through notification.
    checkin, arriveLate ,checkout are data to enable buttons.
    
    It returns the response received.
    """ 
    #Initialize Firebase-Admin
    initialize_firebase()

    # Collect the registration token from employee doctype for the given list of employees
    registration_token = frappe.get_value("Employee", {"name": employee_id}, "fcm_token")
    
    # Create message payload. 
    if registration_token :
        message = messaging.Message(
                data= {
                "title": title,
                "body" : body,
                "showButtonCheckIn": checkin,
                "showButtonCheckOut": checkout,
                "showButtonArrivingLate": arriveLate
                },
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            badge=0,
                            mutable_content= 1,
                            category = "oneFmNotificationCategory1"
                        ),
                    ),
                ),
                token=registration_token,
            )
        response = messaging.send(message)
    return response

@frappe.whitelist()
def push_notification_rest_api_for_checkin(employee_id, title, body, checkin, arriveLate ,checkout ):
    """ 
    This function is used to send notification through Firebase CLoud Message. 
    It is a rest API that sends request to frappe.get_site_config().get("firebase_api")
    
    Params: employee_id e.g. HR_EMP_00001, , title:"Title of your message", body:"Body of your message"

    serverToken is fetched from firebase -> project settings -> Cloud Messaging -> Project credentials
    Device Token and Device OS is store in employee doctype using 'store_fcm_token' on device end.
    """
    
    try:
        initialize_firebase()
        employee_data = frappe.db.get_value("Employee", {"employee_id": employee_id}, ["fcm_token", "device_os"],as_dict=1)
        if not employee_data:
            employee_data = frappe.db.get_value("Employee", employee_id, ["fcm_token", "device_os"],as_dict=1)
        deviceToken = employee_data.fcm_token
        device_os = employee_data.device_os
        
        #Body in json form defining a message payload to send through API. 
        # The parameter defers based on OS. Hence Body is designed based on the OS of the device.
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            token=deviceToken
        )
        res = messaging.send(message)
        return v1_api.utils.response("success", 200, {'response': str(res)})
    except Exception as e:
        return v1_api.utils.response("error", 500, {}, str(e))

@frappe.whitelist()
def push_notification_rest_api_for_leave_application(employee_id, title, body, leave_id):
    """ 
    This function is used to send notification through Firebase CLoud Message. 
    It is a rest API that sends request to frappe.get_site_config().get("firebase_api")
    
    Params: employee_id e.g. HR_EMP_00001, , title:"Title of your message", body:"Body of your message", leave_id: Leave Application ID

    serverToken is fetched from firebase -> project settings -> Cloud Messaging -> Project credentials
    Device Token and Device OS is store in employee doctype using 'store_fcm_token' on device end.
    """
    try:
        initialize_firebase()
        employee_data = frappe.db.get_value("Employee", employee_id, ["fcm_token", "device_os"],as_dict=1)
        deviceToken = employee_data.fcm_token
        device_os = employee_data.device_os
        
        #Body in json form defining a message payload to send through API. 
        # The parameter defers based on OS. Hence Body is designed based on the OS of the device.
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            token=deviceToken
        )
        res = messaging.send(message)
        return v1_api.utils.response("success", 200, {'response': str(res)})
    except Exception as e:
        return v1_api.utils.response("error", 500, {}, str(e))
    