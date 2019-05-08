import os
import logging
from datetime import timedelta, datetime
import binascii
import collections
import hashlib
import sys
import random
import string
import re
from unicodedata import normalize

from werkzeug.exceptions import HTTPException
from flask import Flask, request, abort, make_response, current_app, jsonify, g
from flask.views import MethodView
app = Flask(__name__)

from six.moves.urllib.parse import quote

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


BUCKET_IMAGES = 'exec-trav-storage-images'
BUCKET_FILES = 'exec-trav-storage-files'

DOMAIN_IMAGES = 'images.executivetraveller.com'
DOMAIN_FILES = 'files.executivetraveller.com'

ALLOW_ORIGINS = [
    'www.executivetraveller.com',
    'test.executivetraveller.com',
    'localhost'
]

SIGNED_URL_EXPIRES_SECONDS = 900 # 15 minutes


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
                "filepath": filepath,
                "original_url": url
            }
        }
        """
        filename = request.args.get('filename')
        if not filename:
            return make_response_validation_error('filename', message='Parameter filename is required')

        # generate a unique file path for new file uploads
        # year/month/random/slug.extension
        datetime_now = datetime.utcnow()
        salt = random_hash()
        filename, file_extension = os.path.splitext(filename)
        # remove unicode and other rubbish from filename
        slug = slugify(filename)
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
        signed_url = generate_signed_url(self.bucket, filepath, http_method, SIGNED_URL_EXPIRES_SECONDS)

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
            "filepath": filepath,
            "original_url": "https://{}/{}".format(self.domain, filepath),
            "original_filename": "gs://{}/{}".format(self.bucket, filepath)
        }
        if dynamic_url:
            o['dynamic_url'] = dynamic_url
        return o


class FilesAPI(BaseUpload):
    bucket = BUCKET_FILES
    domain = DOMAIN_FILES


class ImagesAPI(BaseUpload):
    bucket = BUCKET_IMAGES
    domain = DOMAIN_IMAGES

    def post(self):
        """ Create a dynamic serving url

        Returns: {
            "object": {
                "filepath": filepath,
                "original_url": url,
                "dynamic_url": url
            }
        }
        """
        filepath = request.args.get('filepath')
        if not filepath:
            return make_response_validation_error('filepath', message='Parameter filepath is required')

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


# Add routes to Flask app
app.add_url_rule('/file/upload', view_func=FilesAPI.as_view('upload_file'), methods=['GET', 'OPTIONS'])
app.add_url_rule('/file/delete', view_func=FilesAPI.as_view('delete_file'), methods=['DELETE', 'OPTIONS'])

app.add_url_rule('/image/upload', view_func=ImagesAPI.as_view('upload_image'), methods=['GET', 'OPTIONS'])
app.add_url_rule('/image/dynamic', view_func=ImagesAPI.as_view('get_dynamic'), methods=['POST', 'OPTIONS'])
app.add_url_rule('/image/delete', view_func=ImagesAPI.as_view('delete_image'), methods=['DELETE', 'OPTIONS'])

@app.before_request
def before_request():
    # redirect everything to SSL
    if not request.is_secure:
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

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


# Helpers

def abort_json(status_code, message):
    json_response = jsonify({'message': message})
    json_response.status_code = status_code
    abort(json_response)

def make_response_validation_error(param, location='query', message='There was a input validation error', expected='string'):
    response = jsonify({
        "detail": {
            "location": location,
            "param": param,
            "message": message,
            "example": expected
        }})
    response.status_code = 422
    return response


# Utils

def random_hash(length=6):
    choices = string.ascii_letters + string.digits
    return ''.join(random.choice(choices) for i in range(length))


_punct_re = re.compile(r'[\r\n\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an slightly worse ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize('NFKD', word).encode('ascii', 'ignore')
        if word:
            result.append(unicode(word, 'utf-8'))
    return delim.join(result)


# Code below heavily borrowed from here: https://cloud.google.com/storage/docs/access-control/signing-urls-manually
def generate_signed_url(bucket_name, object_name, http_method, expiration, query_parameters=None, headers=None):
    """ Generate a signed URL for managing GCS objects using the Cloud Storage V4 signing process.
    """
    if expiration > 604800:
        print('Expiration Time can\'t be longer than 604800 seconds (7 days).')
        expiration = 604800

    escaped_object_name = quote(object_name, safe='')
    canonical_uri = '/{}/{}'.format(bucket_name, escaped_object_name)

    datetime_now = datetime.utcnow()
    request_timestamp = datetime_now.strftime('%Y%m%dT%H%M%SZ')
    datestamp = datetime_now.strftime('%Y%m%d')

    client_email = app_identity.get_service_account_name()

    credential_scope = '{}/auto/storage/goog4_request'.format(datestamp)
    credential = '{}/{}'.format(client_email, credential_scope)
    
    if headers is None:
        headers = dict()
        
    headers['host'] = 'storage.googleapis.com'

    canonical_headers = ''
    ordered_headers = collections.OrderedDict(sorted(headers.items()))
    for k, v in ordered_headers.items():
        lower_k = str(k).lower()
        strip_v = str(v).lower()
        canonical_headers += '{}:{}\n'.format(lower_k, strip_v)
            
    signed_headers = ''
    for k, _ in ordered_headers.items():
        lower_k = str(k).lower()
        signed_headers += '{};'.format(lower_k)
    signed_headers = signed_headers[:-1]  # remove trailing '&'

    if query_parameters is None:
        query_parameters = dict()
        
    query_parameters['X-Goog-Algorithm'] = 'GOOG4-RSA-SHA256'
    query_parameters['X-Goog-Credential'] = credential
    query_parameters['X-Goog-Date'] = request_timestamp
    query_parameters['X-Goog-Expires'] = expiration
    query_parameters['X-Goog-SignedHeaders'] = signed_headers

    canonical_query_string = ''
    ordered_query_parameters = collections.OrderedDict(
        sorted(query_parameters.items()))
    for k, v in ordered_query_parameters.items():
        encoded_k = quote(str(k), safe='')
        encoded_v = quote(str(v), safe='')
        canonical_query_string += '{}={}&'.format(encoded_k, encoded_v)
    canonical_query_string = canonical_query_string[:-1]  # remove trailing '&'
    
    canonical_request = '\n'.join([http_method,
                                   canonical_uri,
                                   canonical_query_string,
                                   canonical_headers,
                                   signed_headers,
                                   'UNSIGNED-PAYLOAD'])

    canonical_request_hash = hashlib.sha256(canonical_request.encode()).hexdigest()

    string_to_sign = '\n'.join(['GOOG4-RSA-SHA256',
                                request_timestamp,
                                credential_scope,
                                canonical_request_hash])

    signing_key_name, signature = app_identity.sign_blob(string_to_sign)
    signature = binascii.hexlify(signature).decode()
    
    host_name = 'https://storage.googleapis.com'
    signed_url = '{}{}?{}&X-Goog-Signature={}'.format(host_name, canonical_uri,
                                                      canonical_query_string,
                                                      signature)

    return signed_url