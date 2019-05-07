import os
import logging
from datetime import timedelta
import binascii
import collections
import datetime
import hashlib
import sys

from flask import Flask, request, abort, make_response, current_app, jsonify
from flask.views import MethodView

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
    response = jsonify({
        "detail": {
            "location": location,
            "param": param,
            "message": message,
            "example": expected
        }})
    response.status_code = 422
    return response


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

    def get(self):
        filepath = request.args.get('filepath')
        if not filepath:
            return make_response_validation_error('filepath', message='Parameter filepath is required')

        url = generate_signed_url(BUCKET_UPLOAD, filepath, http_method='PUT')
        
        return url


class ImagesAPI(CrossOrigin):

    # TODO convert to query string with ?filepath=
    # TODO change routes /upload

    def get(self):
        filepath = request.args.get('filepath', '')
        pass

    def post(self):
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

    def delete(self):
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


class FilesAPI(CrossOrigin):

    # TODO convert to query string with ?filepath=
    # TODO change routes /upload

    def get(self):
        """ Returns the file urls for the GCS object

        Returns: {
            "filename": "gs://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "original_url": "https://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "dynamic_url": "https://googly.img/moo-haa-haa-haa.jpeg",
        }
        """
        pass

    def post(self):
        """ Saves file to Google Cloud Storage from upload bucket 
        and generates dynamic serving url

        Returns: {
            "filename": "gs://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "original_url": "https://files.executivetraveller.com/2019/05/hash-my-file-name.jpeg",
            "dynamic_url": "https://googly.img/moo-haa-haa-haa.jpeg",
        }
        """
        pass

    def delete(self):
        """Deletes file from Google Cloud Storage
        """
        pass


app.add_url_rule('/upload', view_func=UploadAPI.as_view('get_upload'), methods=['GET', 'OPTIONS'])
app.add_url_rule('/image/save', view_func=ImagesAPI.as_view('post_image'), methods=['POST', 'OPTIONS'])
app.add_url_rule('/image/links', view_func=ImagesAPI.as_view('get_image'), methods=['GET', 'OPTIONS'])
app.add_url_rule('/image/delete', view_func=ImagesAPI.as_view('delete_image'), methods=['DELETE', 'OPTIONS'])
app.add_url_rule('/file/save', view_func=FilesAPI.as_view('post_file'), methods=['POST', 'OPTIONS'])
app.add_url_rule('/file/links', view_func=FilesAPI.as_view('get_file'), methods=['GET', 'OPTIONS'])
app.add_url_rule('/file/delete', view_func=FilesAPI.as_view('delete_file'), methods=['DELETE', 'OPTIONS'])


#def generate_signed_url(service_account_file, bucket_name, object_name,
def generate_signed_url(bucket_name, object_name, http_method='GET', expiration=SIGNED_URL_EXPIRES_SECONDS, query_parameters=None, headers=None):

    if expiration > 604800:
        print('Expiration Time can\'t be longer than 604800 seconds (7 days).')
        sys.exit(1)

    escaped_object_name = quote(object_name, safe='')
    canonical_uri = '/{}/{}'.format(bucket_name, escaped_object_name)

    datetime_now = datetime.datetime.utcnow()
    request_timestamp = datetime_now.strftime('%Y%m%dT%H%M%SZ')
    datestamp = datetime_now.strftime('%Y%m%d')
    
    #google_credentials = service_account.Credentials.from_service_account_file(service_account_file)
    #client_email = google_credentials.service_account_email

    client_email = app_identity.get_service_account_name()

    print 'service account name', client_email

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

    #signature = binascii.hexlify(google_credentials.signer.sign(string_to_sign)).decode() 
    signing_key_name, signature = app_identity.sign_blob(string_to_sign)
    signature = binascii.hexlify(signature).decode() # not sure if I need to do this?
    
    host_name = 'https://storage.googleapis.com'
    signed_url = '{}{}?{}&X-Goog-Signature={}'.format(host_name, canonical_uri,
                                                      canonical_query_string,
                                                      signature)

    return signed_url