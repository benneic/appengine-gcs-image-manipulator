all: build

run: requirements.txt
	dev_appserver.py app.yaml

requirements.txt: build

build:
	mkdir -p lib
	echo "[install]\nprefix=" > ~/.pydistutils.cfg
	pip install -t lib/ -r requirements.txt
	rm ~/.pydistutils.cfg

clean:
	rm -rf lib

deploy: cors.json requirements.txt
	gcloud app deploy --project=exec-trav-images

cors.json: set-cors

set-cors:
	@echo Updating CORS rules from
	@gsutil cors get gs://public.images.executivetraveller.com
	@echo to
	@cat cors.json
	gsutil cors set cors.json gs://public.images.executivetraveller.com
	