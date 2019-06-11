from datetime import timedelta, datetime
import binascii
import collections
import hashlib
import random
import string
import re
from unicodedata import normalize

from six.moves.urllib.parse import quote

from google.appengine.api import app_identity


def random_hash(length=6):
    choices = string.ascii_lowercase + string.digits
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


def generate_gcs_v4_signed_url(bucket_name, object_name, http_method, expiration, query_parameters=None, headers=None):
    """ Generate a signed URL for managing GCS objects using the Cloud Storage V4 signing process.
    Code below heavily borrowed from here: https://cloud.google.com/storage/docs/access-control/signing-urls-manually
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