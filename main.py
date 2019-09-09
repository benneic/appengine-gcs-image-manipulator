import logging

from werkzeug.exceptions import HTTPException
from flask import Flask, request, jsonify, redirect

from endpoints.gcs import ImagesAPI, FilesAPI

# NOTE
# TLDR; make run
# It is not possible to run this Flask app locally as it depends on libraries and 
# functionality only available in Google App Engine environment
# For testing use the GAE Local Development Server (dev_appserver.py)
# https://cloud.google.com/appengine/docs/standard/python/tools/using-local-server
# See Makefile run command
# Also note that dynamic urls returned by get_serving_url() will not by dynamic
# if returned by the Local Development Server


### Flask WSGI app

app = Flask(__name__)

app.add_url_rule('/upload', view_func=ImagesAPI.as_view('request_upload'), methods=['GET', 'OPTIONS'])
app.add_url_rule('/dynamic', view_func=ImagesAPI.as_view('generate_dynamic'), methods=['POST', 'OPTIONS'])
app.add_url_rule('/delete', view_func=ImagesAPI.as_view('delete_image'), methods=['DELETE', 'OPTIONS'])


# Flask Wrappers

@app.before_request
def before_request_require_ssl():
    # dont require ssl in debug mode
    # to enable debug mode set env var FLASK_ENV = development
    if not app.config['DEBUG'] and not request.is_secure:
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

@app.before_request
def before_request_authenticate():
    #TODO Require some auth
    if not app.config['DEBUG']:
        logging.warn('You should consider adding in some security')
    return

    token = request.headers.get('X-Session-Token')
    if token:
        # TODO Require some type of token and check session against DB
        if token == "token":
            return None
        abort_json(401, "Invalid X-Session-Token")

    token = request.headers.get('X-Application-Secret')
    if token:
        # TODO check against ENV variable?
        if token == "secret":
            return None
        abort_json(401, "Invalid X-Application-Secret")

    abort_json(401, "Please provide authorised credentials")


@app.errorhandler(HTTPException)
def http_exception_handler(error):
    response = error.get_response()
    json_response = jsonify({'message': error.description})
    json_response.status_code = response.status_code
    return json_response

@app.errorhandler(Exception)
def uncaught_exception_handler(error):
    logging.exception(error)
    json_response = jsonify({'message': str(error)})
    json_response.status_code = 500
    return json_response
