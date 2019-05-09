# Image Upload API
with Dynamic Image Resizing 

**Powered by**:
- Google Cloud Storage
- Google App Engine with Images API
- Flask

***TLDR***

This API is used to create dynamic image hosting URLs used for on the fly image resizing and CDN hosting.

## How it works

**Step 1: Get a signed upload URL**

Upload file to a private bucket using signed URL from a browser.

Get a signed URL for a particular file name:

```
GET https://exec-trav-storage.appspot.com/upload?filepath?{path/to/file.jpeg}
```



**Step 2: Browser uploads image directly to private bucket**

Using the signed url and same method using previous step

Make sure you provide correct content-type headers!

```
PUT https://storage.googleapis.com/upload.executivetraveller.com/sample.jpeg?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=exec-trav-storage%40appspot.gserviceaccount.com%2F20190507%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20190507T120129Z&X-Goog-Expires=900&X-Goog-SignedHeaders=host&X-Goog-Signature=13c2e9a8640bd77495f5ccc465ebc0217b961c9a9196b616bb51543b91359ba6722c148f2ecf421ac274748dd341eeabdab3c6adc8a4a28a946eda334fa75ce9bee6ee5e3ab49be416013b5c49c55ebb5dff624c006261d785b3e87fce8c100b25cb682e0a601967db40248195a65ac36d5fb03ca2c78510df89850f9c9d17cab7ee2db510fa0912369655ebc23c9e621b842be3696f04951ca71930d09e4a7b26acf1f876d5e916db5bd5c95b9f45dfe5d688ffd6eb0b45d86e0020da7af77133c940d1ee410187f0a40ca53706a7bcd4784e7327e46630eda52a36ce9e7eb9216b0518d761868e53c349a21a8a2cdb1586c9150443f642768d3d9501a811f1
Content-Type: image/jpeg
Cache-Control: maxage=900

[JPEG-DATA]
```


**Step 3: Move the file from temporary storage to permanent storage and get dynamic link**

Call the images api to generate a dynamic image hosting URL

```
POST https://exec-trav-storage.appspot.com/image/save?filepath?{path/to/file.jpeg}
```


**Step 4: Save dynamic URL to database**





# API Spec

See **Serving URL parameters** section below for the features provided by the dynamic sizing service. Also see here for more info on how this works:
https://cloud.google.com/appengine/docs/standard/python/images/

This application has only two operations that can be performed, **PUT** and **DELETE**. Both require a image in a google cloud storage bucket (currently this is `gs://images.executivetraveller.com`). The bucket must be set up with Owner access for this App Engine project.

The files passed to this API must be valid images with the following extensions (in lower case) with UTF8 encoded file names:
- gif
- png
- jpg
- jpeg
- webp

**GET**

For more info see here: https://cloud.google.com/storage/docs/access-control/signed-urls

**PUT**
Returns an image serving url for the given GCS image object.
Note: It is safe to call this method more than once for the same GCS image object, the same URL will be returned no matter how many times you call it.


```shell
gsutil cp sample.jpeg gs://images.executivetraveller.com/{path/to/file.jpeg}
curl -XPUT https://exec-trav-images.appspot.com/{path/to/file.jpeg}
```
Returns 201 on Success with URL of dynamic image serving url of the image such as https://lh3.googleusercontent.com/examplestring

On failure returns:
    - 403 on AccessDeniedError
    - 404 on ObjectNotFoundError
    - 405 on NotImageError
    - 409 on TransformationError, UnsupportedSizeError or LargeImageError
    - 500 when sommething else happens that needs investigation (here)[https://console.cloud.google.com/errors?service=default&version&time=P1D&order=LAST_SEEN_DESC&resolution=OPEN&project=exec-trav-images&organizationId=1016752747476]

**DELETE**
Removes an image serving url for the given GCS image object and makes it no longer accessable. This should be done whenever an image is deleted from the GCS bucket. (In the future this should be done automatically using a cloud function)

```shell
gsutil cp sample.jpeg gs://images.executivetraveller.com/{path/to/file.jpeg}
curl -XPUT https://exec-trav-images.appspot.com/{path/to/file.jpeg}
```
Returns 204 on Success.

On failure returns:
    - 403 on AccessDeniedError
    - 404 on ObjectNotFoundError
    - 500 when sommething else happens that needs investigation (here)[https://console.cloud.google.com/errors?service=default&version&time=P1D&order=LAST_SEEN_DESC&resolution=OPEN&project=exec-trav-images&organizationId=1016752747476]


**NOTE**

It's probably not a good idea to depend on any of these options existing forever. Google could remove most of them without notice at any time.
So we should be prepared to update this stuff at a moments notice when things stop working.

## A warning on Google App Engine and Cloud Storage permissions

Make sure when doing this again that the correct permissions are set up for this App Engine project to access the other Google Cloud Storage bucket like so:

`gsutil acl ch -u app-engine-project@appspot.gserviceaccount.com:OWNER gs://other-storage-bucket`

For example
```
gsutil acl ch -u executive-traveller-storage@appspot.gserviceaccount.com:OWNER gs://exec-trav-images-asia
```

Or add Storage Legacy Bucket Owner and Storage Owner permission in the Console UI for the same user.

While testing this application I was receiving a TransformationError exception until I had resolved these permissions. Ensure that the has resource level permissioning, otherwise this is not possible using the new bucket level permissions.

## Serving URL parameters

We can effect various image transformations by tacking strings onto the end of an App Engine blob-based image URL, following an = character. Options can be combined by separating them with hyphens, eg.:

http://{image-url}=s200-fh-p-b10-c0xFFFF0000
or:

http://{image-url}=s200-r90-cc-c0xFF00FF00-fSoften=1,20,0:


### SIZE / CROP
s640 — generates image 640 pixels on largest dimension
s0 — original size image
w100 — generates image 100 pixels wide
h100 — generates image 100 pixels tall
s (without a value) — stretches image to fit dimensions
c — crops image to provided dimensions
n — same as c, but crops from the center
p — smart square crop, attempts cropping to faces
pp — alternate smart square crop, does not cut off faces (?)
cc — generates a circularly cropped image
ci — square crop to smallest of: width, height, or specified =s parameter
nu — no-upscaling. Disables resizing an image to larger than its original resolution.

### PAN AND ZOOM
x, y, z: — pan and zoom a tiled image. These have no effect on an untiled image or without an authorization parameter of some form (see googleartproject.com).

### ROTATION
fv — flip vertically
fh — flip horizontally
r{90, 180, 270} — rotates image 90, 180, or 270 degrees clockwise

### IMAGE FORMAT
rj — forces the resulting image to be JPG
rp — forces the resulting image to be PNG
rw — forces the resulting image to be WebP
rg — forces the resulting image to be GIF
v{0,1,2,3} — sets image to a different format option (works with JPG and WebP)

Forcing PNG, WebP and GIF outputs can work in combination with circular crops for a transparent background. Forcing JPG can be combined with border color to fill in backgrounds in transparent images.

### ANIMATED GIFs
rh — generates an MP4 from the input image
k — kill animation (generates static image)

### MISC.
b10 — add a 10px border to image
c0xAARRGGBB — set border color, eg. =c0xffff0000 for red
d — adds header to cause browser download
e7 — set cache-control max-age header on response to 7 days
l100 — sets JPEG quality to 100% (1-100)
h — responds with an HTML page containing the image
g — responds with XML used by Google's pan/zoom

### Filters
fSoften=1,100,0: - where 100 can go from 0 to 100 to blur the image
fVignette=1,100,1.4,0,000000 where 100 controls the size of the gradient and 000000 is RRGGBB of the color of the border shadow
fInvert=0,1 inverts the image regardless of the value provided
fbw=0,1 makes the image black and white regardless of the value provided
Unknown Parameters
These parameters have been seen in use, but their effect is unknown: no, nd, mv

### Caveats
Some options (like =l for JPEG quality) do not seem to generate new images. If you change another option (size, etc.) and change the l value, the quality change should be visible. Some options also don't work well together. This is all undocumented by Google, probably with good reason.


## Full list of params

Notes:

bool means just add the variable by itself
int means number after variable name
string means (potentially complex) string after variable name
hex means hexidecimal number in format 0x000000 after variable name
variables are separated by hyphens (-)

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

### Detailed v option investigation

Someday, while I was investigating the image response headers, I found an attribute etag with value set to v1. Since I haven't seen any v option yet, I just tried adding it to the image url and it worked! Despite the header attribute value probably has nothing to do with the v option, it helped me to accidentally find it.

#### Investigating how the effect works
First, I've noticed that setting v0 and not setting v resulted in the same response, which indicates that v0 returns the original image with no v option (just like using s0 on the s option would return the original sizing).

Then, I've noticed that setting v1, v2, and v3 progressively returned an image with a smaller content size (weight), and visually it became poorer. Interestingly, setting v4, v5, etc, didn't continue to optimize it.

#### Investigating what the effect is
Some other day I tested the same parameters on another image, and found that nothing happened. That was interesting: an option that works for an image and doesn't work for another, so I started testing what was the difference between the images. Reviewing the list of parameters, it came to me that it could be the image type, and indeed it was! The first image type I've tried the v option was JPEG, and the second was PNG. So, I could reproduce the same effect by setting the second one with both rj and v3!

Hence, I searched internet about JPEG types, and interestingly I've found some sources (as you can see here, and here) explaining about 3 types of JPEG: Baseline Standard, Baseline Optimized, and Progressive, perfectly fitting the three variations available within the v options!

#### Investigating when the effect works
I went trying the same v option on other image types, and found that WebP also supported the same kind of customized type, also progressively optimizing the image in weight and quality (but much lesser in quality than JPEG) in the same range between v0 and v3. Unfortunately, I haven't yet found any sources of different WebP types.

Also, it didn't change anything when used on GIFs, but, as the PNG type, you can also combine its options with rj and v3, but you would (of course) lose the GIF animation and quality.




### TODO look at browser file uploads using anonymous uploads and Firebase SDK

Using Anonymous login with Firebase SDK

https://firebase.google.com/docs/storage/

https://github.com/firebase/quickstart-js/blob/master/storage/index.html