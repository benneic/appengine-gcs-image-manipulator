import os
import logging
from datetime import timedelta, datetime

from flask import request, abort, make_response, current_app, jsonify
from flask.views import MethodView


from six.moves.urllib.parse import quote

from google.appengine.api import images, app_identity
from google.appengine.ext import blobstore
import cloudstorage
cloudstorage.set_default_retry_params(
    cloudstorage.RetryParams(
        initial_delay=0.2, max_delay=5.0, backoff_factor=2, max_retry_period=15
        ))

from . import utils


BUCKET_IMAGES = 'exec-trav-images-asia'
BUCKET_FILES = 'exec-trav-files-asia'

DOMAIN_IMAGES = 'images.executivetraveller.com'
DOMAIN_FILES = 'files.executivetraveller.com'

# restrict uploads to these extensions
EXTENSIONS_IMAGES = ['.webp','.jpg','.jpeg','.png','.gif'] # . must be included for comparrison to splitext()
EXTENSIONS_FILES = ['.pdf'] # . must be included for comparrison to splitext()

ALLOW_ORIGINS = [
    'www.executivetraveller.com',
    'test.executivetraveller.com',
    'localhost'
]

SIGNED_URL_EXPIRES_SECONDS = 900 # 15 minutes
FILEPATH_HASH_LENGTH = 8


def abort_json(status_code, message):
    json_response = jsonify({"error":{"kind":"abort", "message": message}})
    json_response.status_code = status_code
    abort(json_response)

def make_response_validation_error(param, location='query', message='There was a input validation error', expected='string'):
    response = jsonify({
        "error": {
            "kind": "validation",
            "location": location,
            "param": param,
            "message": message,
            "example": expected
        }})
    response.status_code = 422
    return response


class BaseUpload(MethodView):

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

    def get(self):
        """ Creates a signed URL for uploading a image/file object to Google Cloud Storage

        Returns: {
            "upload": {
                "method": http_method,
                "url": signed_url,
                "timestamp": request_timestamp,
                "expires": expiration
            },
            "object": {
                "path": filepath in gcs bucket,
                "location": storage bucket and path,
                "url": url to access the file via https
            }
        }
        """
        filename = request.args.get('filename')
        if not filename:
            return make_response_validation_error('filename', message='Parameter filename is required')

        datetime_now = datetime.utcnow()

        # generate a unique file path for new file uploads
        salt = utils.random_hash(FILEPATH_HASH_LENGTH)

        filename = os.path.basename(filename)
        filename, file_extension = os.path.splitext(filename)

        if file_extension not in self.extensions:
            message = f"Parameter filename has an invalid extension, please only send {self.extensions}"
            return make_response_validation_error('filename', message=message)

        # remove unicode and other rubbish from filename
        slug = utils.slugify(filename)

        # assemble filepath based on year/month/randomsalt/slug.extension
        filepath = "{}/{}/{}/{}{}".format(
            datetime_now.year,
            datetime_now.strftime('%m'),
            salt,
            slug,
            file_extension
        )

        http_method = 'PUT'
        expires = datetime_now + timedelta(seconds=SIGNED_URL_EXPIRES_SECONDS)

        # generate the signed url
        signed_url = utils.generate_gcs_v4_signed_url(self.bucket, filepath, http_method, SIGNED_URL_EXPIRES_SECONDS)

        response = jsonify({
            "upload": {
                "method": http_method,
                "url": signed_url,
                "expires": expires.isoformat()
            },
            "object": self._object_schema(filepath)
        })
        return response

    def _object_schema(self, filepath, dynamic_url=None):
        o = {
            "path": filepath,
            "url": "https://{}/{}".format(self.domain, filepath),
            "location": "gs://{}/{}".format(self.bucket, filepath)
        }
        if dynamic_url:
            o['dynamic_url'] = dynamic_url
        return o

    def delete(self):
        """Delete the original file and dynamic serving url if it exists
        """
        filepath = request.args.get('filepath')
        if not filepath:
            return make_response_validation_error('filepath', message='Parameter filepath is required')

        try:
            cloudstorage.delete(filename)
        except cloudstorage.AuthorizationError:
            abort_json(401, "Unauthorized request has been received by GCS.")
        except cloudstorage.ForbiddenError:
            abort_json(403, "Cloud Storage Forbidden Error. GCS replies with a 403 error for many reasons, the most common one is due to bucket permission not correctly setup for your app to access.")
        except cloudstorage.NotFoundError:
            abort_json(404, filepath + " not found on GCS in bucket " + self.bucket)
        except cloudstorage.TimeoutError:
            abort_json(408, 'Remote timed out')

        # TODO get the query string and delete file if asked to
        blobstore_filename = u'/gs/{}/{}'.format(bucket_name, filepath)
        blob_key = blobstore.create_gs_key(blobstore_filename)
        try:
            images.delete_serving_url(blob_key)
        except images.AccessDeniedError:
            abort_json(403, "App Engine Images API Access Denied Error. Files has already been deleted from Cloud Storage")
        except images.ObjectNotFoundError:
            pass

        return '', 204


class FilesAPI(BaseUpload):
    bucket = BUCKET_FILES
    domain = DOMAIN_FILES
    extensions = EXTENSIONS_FILES


class ImagesAPI(BaseUpload):
    bucket = BUCKET_IMAGES
    domain = DOMAIN_IMAGES
    extensions = EXTENSIONS_IMAGES

    def post(self):
        """ Create a dynamic serving url

        Returns: {
            "object": {
                "path": filepath in bucket,
                "location": storage bucket and path,
                "url": url to access the file via https
                "dynamic_url": url to access the file with dynamic image handling
            }
        }
        """
        filepath = request.args.get('path')
        if not filepath:
            return make_response_validation_error('path', message='Parameter path is required and should contain the GCS object name')

        blobstore_filename = u'/gs/{}/{}'.format(self.bucket, filepath)
        blob_key = blobstore.create_gs_key(blobstore_filename)

        try:

            dynamic_url = images.get_serving_url(blob_key, secure_url=True)

            # return the dynamic url with the rest of the object data
            response = jsonify({
                "object": self._object_schema(filepath, dynamic_url)
            })
            response.status_code = 201
            return response

        except images.AccessDeniedError:
            abort_json(403, u"App Engine Images API Access Denied Error. Files has already been deleted from Cloud Storage")
        except images.ObjectNotFoundError:
            abort_json(404, u"App Engine Images API could not find " + filepath + " in Cloud Storage bucket " + self.bucket)
        except images.NotImageError:
            abort_json(405, u"App Engine Images API says " + filepath + " is not an image")
        except (images.TransformationError, images.UnsupportedSizeError, images.LargeImageError) as e:
            logging.exception('Requires investigation')
            abort_json(409, str(e))
