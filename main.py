import os
import logging
from datetime import timedelta
from functools import update_wrapper

from flask import Flask, request, abort, make_response, current_app, MethodView

from google.appengine.api import images, app_identity
from google.appengine.ext import blobstore
import cloudstorage

cloudstorage.set_default_retry_params(
    cloudstorage.RetryParams(
        initial_delay=0.2, max_delay=5.0, backoff_factor=2, max_retry_period=15
        ))

# NOTE
# TLDR; make run
# It is not possible to run this Flask app locally as it depends on libraries and 
# functionality only available in Google App Engine environment
# For testing please use the GAE Local Development Server (dev_appserver.py)
# https://cloud.google.com/appengine/docs/standard/python/tools/using-local-server
# See Makefile run command
# Also note that dynamic urls returned by get_serving_url() will not by dynamic
# if returned by the Local Development Server


app = Flask(__name__)

BUCKET_UPLOAD = os.environ.get('BUCKET_UPLOAD', 'upload.executivetraveller.com')
BUCKET_IMAGES = os.environ.get('BUCKET_IMAGES', 'images.executivetraveller.com')
BUCKET_FILES = os.environ.get('BUCKET_FILES', 'files.executivetraveller.com')

ALLOW_ORIGINS = [
    'www.executivetraveller.com',
    'test.executivetraveller.com',
    'localhost'
]

SIGNED_URL_EXPIRES_SECONDS = 900 # 15 minutes


def make_response_validation_error(param, location='query', message='There was a input validation error', expected='string'):
    return make_response({
        "detail": {
            "location": location,
            "param": param,
            "message": message,
            "example": expected
        }}, 422)


class CrossOrigin(MethodView):

    def options(self):
        """ Allow CORS for specific origins
        """
        resp = current_app.make_default_options_response()
        # Allow our origins (can be multiple)
        resp.headers.extend([('Access-Control-Allow-Origin', origin) for origin in ALLOW_ORIGINS])
        # Allow the actual method
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE'
        # Allow for 60 seconds
        resp.headers['Access-Control-Max-Age'] = "60"

        # 'preflight' request contains the non-standard headers the real request will have (like X-Api-Key)
        # NOTE we can filter out headers we dont want to allow here if we wanted to
        request_headers = request.headers.get('Access-Control-Request-Headers')
        if request_headers:
            resp.headers['Access-Control-Allow-Headers'] = request_headers
 
        return resp


class UploadAPI(CrossOrigin):
    """ Generate a signed upload URL that can be used to POST a file to a temporary
    cloud storage bucket.
    """

    def get(self, filepath):
        filepath = request.args.get('filepath')
        if not filepath:
            return make_response_validation_error('filepath', message='Parameter filepath is required')

        
        pass


class ImagesAPI(CrossOrigin):

    # TODO convert to query string with ?filepath=
    # TODO change routes /upload

    def get(self, filepath):
        filepath = request.args.get('filepath', '')
        pass

    def post(self, filepath):
        """ Create a dynamic serving url
        """
        try:
            url = images.get_serving_url(blob_key, secure_url=True)
            return url, 201
        except images.AccessDeniedError:
            abort(403)
        except images.ObjectNotFoundError:
            abort(404)
        except images.NotImageError:
            abort(405)
        except (images.TransformationError, images.UnsupportedSizeError, images.LargeImageError) as e:
            logging.exception('Requires investigation')
            return str(e), 409

    def delete(self, filepath):
        """Delete dynamic url and optionally the original image
        """
        # TODO get the query string and delete file if asked to
        blobstore_filename = u'/gs/{}/{}'.format(bucket_name, filepath)
        blob_key = blobstore.create_gs_key(blobstore_filename)
        try:
            images.delete_serving_url(blob_key)
            return '', 204
        except images.AccessDeniedError:
            abort(403)
        except images.ObjectNotFoundError:
            abort(404)


class ImagesAPI(CrossOrigin):

    # TODO convert to query string with ?filepath=
    # TODO change routes /upload

    def get(self, filepath):
        """ Returns the file urls for the GCS object

        Returns: {
            "filename": "gs://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "original_url": "https://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "dynamic_url": "https://googly.img/moo-haa-haa-haa.jpeg",
        }
        """
        pass

    def post(self, filepath):
        """ Saves file to Google Cloud Storage from upload bucket 
        and generates dynamic serving url

        Returns: {
            "filename": "gs://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "original_url": "https://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "dynamic_url": "https://googly.img/moo-haa-haa-haa.jpeg",
        }
        """
        pass

    def delete(self, filepath):
        """Deletes file from Google Cloud Storage
        """
        pass


app.add_url_rule('/upload', view_func=UploadAPI.as_view(), methods=['GET', 'OPTIONS'])
app.add_url_rule('/image/save', view_func=ImagesAPI.as_view(), methods=['POST', 'OPTIONS'])
app.add_url_rule('/image/links', view_func=ImagesAPI.as_view(), methods=['GET', 'OPTIONS'])
app.add_url_rule('/image/delete', view_func=ImagesAPI.as_view(), methods=['DELETE', 'OPTIONS'])
app.add_url_rule('/file/save', view_func=FilesAPI.as_view(), methods=['POST', 'OPTIONS'])
app.add_url_rule('/file/links', view_func=FilesAPI.as_view(), methods=['GET', 'OPTIONS'])
app.add_url_rule('/file/delete', view_func=FilesAPI.as_view(), methods=['DELETE', 'OPTIONS'])


