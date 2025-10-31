from app import app as application
import awsgi
def handler(event, context):
    return awsgi.response(application, event, context)