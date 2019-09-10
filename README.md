# Image Manipulator
#### Dynamic Image Resizing powered by Google App Engine, Google Storage and Flask

This API is a proof of concept to showcase how it is essentially possible to get free image transformations powered by the same services that powers Google Photos.

It demonstrates how to:
- do [signed uploads](https://github.com/benneic/appengine-gcs-image-manipulator/blob/master/endpoints/utils.py#L32) direct from the client to a Google Cloud Storage bucket to optimise for speed (bypassing a webserver or middleware)
- [generate a dynamic url](https://github.com/benneic/appengine-gcs-image-manipulator/blob/master/endpoints/gcs.py#L200-L205) using the Google App Engine Images API and the blobstore module

**Demonstrates use of**:
- Google Cloud Storage
- Google App Engine Standard Python 2.7 Images API
- Flask

For a background in the Image Transforms see here: https://cloud.google.com/appengine/docs/standard/python/images/

## WARNING
This demo is based on the App Engine standard API's only available in Python 2.7 which [ends of life Jan 1, 2020](https://pythonclock.org/) and currently unclear what support will exist in app engine after that.
Also it's probably not a good idea to depend on the main list of image transformationsoptions below as they are undocumented.
While this demo implements some concepts such as CORS and client/app secret keys that could allow it to be used in a production environment, use with caution as none of these has been tested.

## Table Of Contents
1. Workflow for images
2. Intro to Dynamic URL parameters
3. Full list of Dynamic URL Parameters provided by Images API
4. API specification
5. To Do 


# 1. Image upload workflow

In the production config all requests below assume HTTPS and support HTTP/2 but will allow HTTP in debug mode.

### Step 1: Get a signed upload URL

To upload a file you will need signed URL to upload it with. So generate one with the `/upload` endpoint.

EXAMPLE REQUEST
```
> GET /upload?filename=sample.jpeg HTTP/1.1
> Host: appengine-gcs-image-manipulator.appspot.com
> Accept: */*

[NO-BODY]
```
Where the `filename` parameter is the name of the file you will be uploading in the next step.

EXAMPLE RESPONSE
```
< HTTP/1.1 200 OK
< Content-Type: application/json
< Date: Thu, 09 May 2019 03:01:59 GMT
< Server: Google Frontend

{
  "object": {
    "path": "2019/05/sr2h72mc/sample.jpeg",
    "location": "gs://your-storage-bucket/2019/05/sr2h72mc/sample.jpeg",
    "url": "https://yourcdn.example.com/2019/05/sr2h72mc/sample.jpeg"
  },
  "upload": {
    "expires": "2019-05-09T03:16:58.671744",
    "method": "PUT",
    "url": "https://storage.googleapis.com/your-storage-bucket/2019%2F05%2Fsr2h72mc%2Ftesting.jpeg?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=executive-traveller-storage%40appspot.gserviceaccount.com%2F20190509%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20190509T030158Z&X-Goog-Expires=900&X-Goog-SignedHeaders=host&X-Goog-Signature=0f9973cb43298536c9cc96284f4bea5b2b3ae295489b257e898b266d0e06068fdd40323f54ab6f69421958f90307e96a3d9bf87ad6429e5a68d861efc1c934a7e18d0c82384695420ce7b18a8c68a6ebd50f607f66844bb6897f79e24ac2462b1b16525d1e29f344b9dbc695c4d19d743cc18a6054d5e124c6d60795eccd8647569fc2db8dd867552657497b544abbf9a6ea64b94eceb940361473c974968483404efcc811eb15566044fbec2882d83eb2be8d39a6f0e7f733f60d84942fd783923401e994a422fd8a638684da1aeaa9f834aea1610f70d49ffb771d40eb8c095639459009ebd3adadcd82977e3b3fd19cfaeb3d17cab62b227bdacbd0240ff4"
  }
}
```


### Step 2: Upload the image

Upload your file, from the browser, using the signed url and method from step 1

**You must also provide `Content-Type` and `Cache-Control` headers!**

EXAMPLE REQUEST
```
> PUT /your-storage-bucket/2019%2F05%2Fsr2h72mc%2Ftesting.jpeg?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=executive-traveller-storage%40appspot.gserviceaccount.com%2F20190509%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20190509T030158Z&X-Goog-Expires=900&X-Goog-SignedHeaders=host&X-Goog-Signature=0f9973cb43298536c9cc96284f4bea5b2b3ae295489b257e898b266d0e06068fdd40323f54ab6f69421958f90307e96a3d9bf87ad6429e5a68d861efc1c934a7e18d0c82384695420ce7b18a8c68a6ebd50f607f66844bb6897f79e24ac2462b1b16525d1e29f344b9dbc695c4d19d743cc18a6054d5e124c6d60795eccd8647569fc2db8dd867552657497b544abbf9a6ea64b94eceb940361473c974968483404efcc811eb15566044fbec2882d83eb2be8d39a6f0e7f733f60d84942fd783923401e994a422fd8a638684da1aeaa9f834aea1610f70d49ffb771d40eb8c095639459009ebd3adadcd82977e3b3fd19cfaeb3d17cab62b227bdacbd0240ff4  HTTP/1.1
> Host: storage.googleapis.com
> Content-Type: image/jpeg
> Cache-Control: maxage=345600

[JPEG-DATA]
```
It is a good idea to tell browsers to cache details of images for a while since they will likely not change so Cache-Control: maxage=345600 is 4 days but do what works for you...


EXAMPLE RESPONSE
```
< HTTP/1.1 200 OK

[NO-BODY]
```

### Step 3: Generate a dynamic hosting url for the image

Call the images api to generate a dynamic image hosting URL, using the object path returned in step 1

EXAMPLE REQUEST
```
> POST /dynamic?path=2019%2F05%2Fsr2h72mc%2Fsample.jpeg HTTP/1.1
> Host: appengine-gcs-image-manipulator.appspot.com
> Accept: */*

[NO-BODY]
```

EXAMPLE RESPONSE
```
< HTTP/1.1 201 Created
< Content-Type: application/json

{
  "object": {
    "dynamic_url": "https://lh3.googleusercontent.com/rYLb3WVrsSeBOiKi9hSDfN2r0ifUfdi8-DIMCmQVSb6d-xXcdYHSYfBUv-AZF_mj1OsK-iq6IPajkfNusm8osGrfM16CsNee6KYeRxN_7WMGSA=s1600",
    "location": "gs://your-storage-bucket/2019/05/sr2h72mc/sample.jpeg",
    "path": "2019/05/sr2h72mc/sample.jpeg",
    "url": "https://yourcdn.example.com/2019/05/sr2h72mc/sample.jpeg"
  }
}
```

### Step 4: Save dynamic URL to your database
Submit the URL in a form from your browser or whatever means necessary to keep a record of it. However calling the `/dynamic` will always return the same URL so you can safely request it again for the same cloud storage file, however this will use up your quotas and limits which is pointless.


# 2. Intro to Dynamic URL parameters

We can effect various image transformations by tacking strings onto the end of an App Engine blob-based image URL, following an = character. Options can be combined by separating them with hyphens, eg.:

https://{dynamic_url}=s200-fh-p-b10-c0xFFFF0000
or:

https://{dynamic_url}=s200-r90-cc-c0xFF00FF00-fSoften=1,20,0:

**NOTE MAX SIZE** is 1600px on longest size

See here for more info on how this works:
https://cloud.google.com/appengine/docs/standard/python/images/


## SIZE / CROP
* s640 — generates image 640 pixels on largest dimension
* s0 — original size image
* w100 — generates image 100 pixels wide
* h100 — generates image 100 pixels tall
* s (without a value) — stretches image to fit dimensions
* c — crops image to provided dimensions
* n — same as c, but crops from the center
* p — smart square crop, attempts cropping to faces
* pp — alternate smart square crop, does not cut off faces (?)
* cc — generates a circularly cropped image
* ci — square crop to smallest of: width, height, or specified =s parameter
* nu — no-upscaling. Disables resizing an image to larger than its original resolution.

## PAN AND ZOOM
* x, y, z: — pan and zoom a tiled image. These have no effect on an untiled image or without an authorization parameter of some form (see googleartproject.com).

## ROTATION
* fv — flip vertically
* fh — flip horizontally
* r{90, 180, 270} — rotates image 90, 180, or 270 degrees clockwise

## IMAGE FORMAT
* rj — forces the resulting image to be JPG
* rp — forces the resulting image to be PNG
* rw — forces the resulting image to be WebP
* rg — forces the resulting image to be GIF
* v{0,1,2,3} — sets image to a different format option (works with JPG and WebP)

Forcing PNG, WebP and GIF outputs can work in combination with circular crops for a transparent background. Forcing JPG can be combined with border color to fill in backgrounds in transparent images.

## ANIMATED GIFs
* rh — generates an MP4 from the input image
* k — kill animation (generates static image)

## MISC.
* b10 — add a 10px border to image
* c0xAARRGGBB — set border color, eg. =c0xffff0000 for red
* d — adds header to cause browser download
* e7 — set cache-control max-age header on response to 7 days
* l100 — sets JPEG quality to 100% (1-100)
* h — responds with an HTML page containing the image
* g — responds with XML used by Google's pan/zoom

## Filters
* fSoften=1,100,0: - where 100 can go from 0 to 100 to blur the image
* fVignette=1,100,1.4,0,000000 where 100 controls the size of the gradient and 000000 is RRGGBB of the color of the border shadow
* fInvert=0,1 inverts the image regardless of the value provided
* fbw=0,1 makes the image black and white regardless of the value provided

## Unknown Parameters
These parameters have been seen in use, but their effect is unknown: no, nd, mv

## Caveats
Some options (like =l for JPEG quality) do not seem to generate new images. If you change another option (size, etc.) and change the l value, the quality change should be visible. Some options also don't work well together. This is all undocumented by Google, probably with good reason.

# 3. Full list of Dynamic URL Parameters

```
bool   - means just add the variable by itself
int    - means number after variable name
string - means (potentially complex) string after variable name
hex    - means hexidecimal number in format 0x000000 after variable name
variables are separated by hyphens (-)
```

```javascript
int:  s   ==> Size
int:  w   ==> Width
bool: c   ==> Crop
hex:  c   ==> BorderColor
bool: d   ==> Download
int:  h   ==> Height
bool: s   ==> Stretch
bool: h   ==> Html
bool: p   ==> SmartCrop
bool: pa  ==> PreserveAspectRatio
bool: pd  ==> Pad
bool: pp  ==> SmartCropNoClip
bool: pf  ==> SmartCropUseFace
int:  p   ==> FocalPlane
bool: n   ==> CenterCrop
int:  r   ==> Rotate
bool: r   ==> SkipRefererCheck
bool: fh  ==> HorizontalFlip
bool: fv  ==> VerticalFlip
bool: cc  ==> CircleCrop
bool: ci  ==> ImageCrop
bool: o   ==> Overlay
str:  o   ==> EncodedObjectId
str:  j   ==> EncodedFrameId
int:  x   ==> TileX
int:  y   ==> TileY
int:  z   ==> TileZoom
bool: g   ==> TileGeneration
bool: fg  ==> ForceTileGeneration
bool: ft  ==> ForceTransformation
int:  e   ==> ExpirationTime
str:  f   ==> ImageFilter
bool: k   ==> KillAnimation
int:  k   ==> FocusBlur
bool: u   ==> Unfiltered
bool: ut  ==> UnfilteredWithTransforms
bool: i   ==> IncludeMetadata
bool: ip  ==> IncludePublicMetadata
bool: a   ==> EsPortraitApprovedOnly
int:  a   ==> SelectFrameint
int:  m   ==> VideoFormat
int:  vb  ==> VideoBegin
int:  vl  ==> VideoLength
bool: lf  ==> LooseFaceCrop
bool: mv  ==> MatchVersion
bool: id  ==> ImageDigest
int:  ic  ==> InternalClient
bool: b   ==> BypassTakedown
int:  b   ==> BorderSize
str:  t   ==> Token
str:  nt0 ==> VersionedToken
bool: rw  ==> RequestWebp
bool: rwu ==> RequestWebpUnlessMaybeTransparent
bool: rwa ==> RequestAnimatedWebp
bool: nw  ==> NoWebp
bool: rh  ==> RequestH264
bool: nc  ==> NoCorrectExifOrientation
bool: nd  ==> NoDefaultImage
bool: no  ==> NoOverlay
str:  q   ==> QueryString
bool: ns  ==> NoSilhouette
int:  l   ==> QualityLevel
int:  v   ==> QualityBucket
bool: nu  ==> NoUpscale
bool: rj  ==> RequestJpeg
bool: rp  ==> RequestPng
bool: rg  ==> RequestGif
bool: pg  ==> TilePyramidAsProto
bool: mo  ==> Monogram
bool: al  ==> Autoloop
int:  iv  ==> ImageVersion
int:  pi  ==> PitchDegrees
int:  ya  ==> YawDegrees
int:  ro  ==> RollDegrees
int:  fo  ==> FovDegrees
bool: df  ==> DetectFaces
str:  mm  ==> VideoMultiFormat
bool: sg  ==> StripGoogleData
bool: gd  ==> PreserveGoogleData
bool: fm  ==> ForceMonogram
int:  ba  ==> Badge
int:  br  ==> BorderRadius
hex:  bc  ==> BackgroundColor
hex:  pc  ==> PadColor
hex:  sc  ==> SubstitutionColor
bool: dv  ==> DownloadVideo
bool: md  ==> MonogramDogfood
int:  cp  ==> ColorProfile
bool: sm  ==> StripMetadata
int:  cv  ==> FaceCropVersion
```

## Detailed v option investigation

Someday, while I was investigating the image response headers, I found an attribute etag with value set to v1. Since I haven't seen any v option yet, I just tried adding it to the image url and it worked! Despite the header attribute value probably has nothing to do with the v option, it helped me to accidentally find it.

## Investigating how the effect works
First, I've noticed that setting v0 and not setting v resulted in the same response, which indicates that v0 returns the original image with no v option (just like using s0 on the s option would return the original sizing).

Then, I've noticed that setting v1, v2, and v3 progressively returned an image with a smaller content size (weight), and visually it became poorer. Interestingly, setting v4, v5, etc, didn't continue to optimize it.

## Investigating what the effect is
Some other day I tested the same parameters on another image, and found that nothing happened. That was interesting: an option that works for an image and doesn't work for another, so I started testing what was the difference between the images. Reviewing the list of parameters, it came to me that it could be the image type, and indeed it was! The first image type I've tried the v option was JPEG, and the second was PNG. So, I could reproduce the same effect by setting the second one with both rj and v3!

Hence, I searched internet about JPEG types, and interestingly I've found some sources (as you can see here, and here) explaining about 3 types of JPEG: Baseline Standard, Baseline Optimized, and Progressive, perfectly fitting the three variations available within the v options!

## Investigating when the effect works
I went trying the same v option on other image types, and found that WebP also supported the same kind of customized type, also progressively optimizing the image in weight and quality (but much lesser in quality than JPEG) in the same range between v0 and v3. Unfortunately, I haven't yet found any sources of different WebP types.

Also, it didn't change anything when used on GIFs, but, as the PNG type, you can also combine its options with rj and v3, but you would (of course) lose the GIF animation and quality.


# 4. API Specification


## GET /upload
Images accepts file extensions: ['.webp','.jpg','.jpeg','.png','.gif']

```
curl https://appengine-gcs-image-manipulator.appspot.com/upload?filename=sample.jpeg
```

### 200 on Success
```
{
  "object": {
    "path": "2019/05/sr2h72mc/sample.jpeg",
    "location": "gs://your-storage-bucket/2019/05/sr2h72mc/sample.jpeg",
    "url": "https://yourcdn.example.com/2019/05/sr2h72mc/sample.jpeg"
  },
  "upload": {
    "expires": "2019-05-09T03:16:58.671744",
    "method": "PUT",
    "url": "https://storage.googleapis.com/your-storage-bucket/2019%2F05%2Fsr2h72mc%2Ftesting.jpeg?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=executive-traveller-storage%40appspot.gserviceaccount.com%2F20190509%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20190509T030158Z&X-Goog-Expires=900&X-Goog-SignedHeaders=host&X-Goog-Signature=0f9973cb43298536c9cc96284f4bea5b2b3ae295489b257e898b266d0e06068fdd40323f54ab6f69421958f90307e96a3d9bf87ad6429e5a68d861efc1c934a7e18d0c82384695420ce7b18a8c68a6ebd50f607f66844bb6897f79e24ac2462b1b16525d1e29f344b9dbc695c4d19d743cc18a6054d5e124c6d60795eccd8647569fc2db8dd867552657497b544abbf9a6ea64b94eceb940361473c974968483404efcc811eb15566044fbec2882d83eb2be8d39a6f0e7f733f60d84942fd783923401e994a422fd8a638684da1aeaa9f834aea1610f70d49ffb771d40eb8c095639459009ebd3adadcd82977e3b3fd19cfaeb3d17cab62b227bdacbd0240ff4"
  }
}
```
Then use the upload.url and upload.method to push file directly into cloud storage

### 422 on Validation error
```
{
  "error": {
    "kind": "validation",
    "example":"string",
    "location":"query",
    "message":"Parameter filename is required",
    "param":"filename"
  }
}
```


## DELETE /delete
Removes an image serving url for the given GCS image object and makes it no longer accessable. This should be done whenever an image is deleted from the GCS bucket. (In the future this should be done automatically using a cloud function)

```shell
gsutil cp sample.jpeg gs://your-storage-bucket/2019/05/sr2h72mc/sample.jpeg
curl -XDELETE https://appengine-gcs-image-manipulator.appspot.com/dynamic?path=2019%2F05%2Fsr2h72mc%2Fsample.jpeg
```
### 204 on Success
No response

### On Failure
On failure returns:
- 401 on UnauthorisedRequest
- 403 on AccessDeniedError
- 404 on ObjectNotFoundError
- 408 on TimeoutError
- 500 when sommething else happens that needs investigation [here](https://console.cloud.google.com/errors?service=default&version&time=P1D&order=LAST_SEEN_DESC&resolution=OPEN&project=executive-traveller-storage&organizationId=1016752747476)


## POST /dynamic
Returns an image serving url for the given GCS image object.
Note: It is safe to call this method more than once for the same GCS image object, the same URL will be returned no matter how many times you call it.


```shell
gsutil cp sample.jpeg gs://your-storage-bucket/2019/05/sr2h72mc/sample.jpeg
curl -XPUT https://appengine-gcs-image-manipulator.appspot.com/dynamic?path=2019%2F05%2Fsr2h72mc%2Fsample.jpeg
```

### 201 on Success
```
{
  "object": {
    "dynamic_url": "https://lh3.googleusercontent.com/rYLb3WVrsSeBOiKi9hSDfN2r0ifUfdi8-DIMCmQVSb6d-xXcdYHSYfBUv-AZF_mj1OsK-iq6IPajkfNusm8osGrfM16CsNee6KYeRxN_7WMGSA=s1600",
    "location": "gs://your-storage-bucket/2019/05/sr2h72mc/sample.jpeg",
    "path": "2019/05/sr2h72mc/sample.jpeg",
    "url": "https://yourcdn.example.com/2019/05/sr2h72mc/sample.jpeg"
  }
}
```

### On Failure
Multiple errors could occur:
- 403 on AccessDeniedError
- 404 on ObjectNotFoundError
- 405 on NotImageError
- 409 on TransformationError, UnsupportedSizeError or LargeImageError
- 500 when sommething else happens that needs investigation [here](https://console.cloud.google.com/errors?service=default&version&time=P1D&order=LAST_SEEN_DESC&resolution=OPEN&project=executive-traveller-storage&organizationId=1016752747476)
```
{
  "error": {
    "kind": "abort",
    "message":"Parameter filename is required"
  }
}
```


## A warning on Google App Engine and Cloud Storage permissions

Make sure when doing this again that the correct permissions are set up for this App Engine project to access the other Google Cloud Storage bucket like so:

`gsutil acl ch -u app-engine-project@appspot.gserviceaccount.com:OWNER gs://other-storage-bucket`

For example
```
gsutil acl ch -u executive-traveller-storage@appspot.gserviceaccount.com:OWNER gs://your-storage-bucket
```

Or add Storage Legacy Bucket Owner and Storage Owner permission in the Console UI for the same user.

While testing this application I was receiving a TransformationError exception until I had resolved these permissions. Ensure that the has resource level permissioning, otherwise this is not possible using the new bucket level permissions.

# 5. TODO

Add API tokens and AUTH.

## Firebase

Look at authentication all users with Firebase then using Firebase SDK to upload files directly to GCS.

Otherwise if not using Firebase Auth look at allowing uploads from browser using anonymous authentication and Firebase SDK

https://firebase.google.com/docs/storage/

https://github.com/firebase/quickstart-js/blob/master/storage/index.html
