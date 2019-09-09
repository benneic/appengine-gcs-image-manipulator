ROOT	:= $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
HUB     := benneic
REPO	:= appengine-gcs-image-manipulator
DATE    := `date "+%Y-%m-%d"`
PROJECT := gcp-project-name

# echo output in cyan
define cecho
	@tput setaf 6
	@echo $1
	@tput sgr0
endef

all: build

.PHONY: debug
debug:
	$(call cecho, "Running in debug mode")
	dev_appserver.py app-debug.yaml

.PHONY: run
run: requirements.txt
	$(call cecho, "Running in production mode")
	dev_appserver.py app.yaml

requirements.txt: build

.PHONY: build
build:
	$(call cecho, "Work around for Mac OSX")
	mkdir -p lib
	echo "[install]\nprefix=" > ~/.pydistutils.cfg
	pip install -t lib/ -r requirements.txt
	rm ~/.pydistutils.cfg

.PHONY: clean
clean:
	rm -rf lib
	rm *.pyc

.PHONY: deploy
deploy: 
	gcloud app deploy --project=$(PROJECT) -v 1

.PHONY: logs
logs:
	gcloud app logs tail --project=$(PROJECT)

.PHONY: config
config:
	test `gcloud config get-value project 2>/dev/null` = default || gcloud config configurations activate default
	