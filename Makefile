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
	rm *.pyc

deploy: 
	gcloud app deploy --project=exec-trav-storage -v 1

logs:
	gcloud app logs tail --project=exec-trav-storage

config:
	test `gcloud config get-value project 2>/dev/null` = default || gcloud config configurations activate default
	