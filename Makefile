ifndef VERBOSE
MAKEFLAGS += --no-print-directory
endif
SHELL := /bin/bash
.DEFAULT_GOAL := help

dockernetwork create:
	@ docker network create lambda-local

dockerrun start:
	@ docker run -p 8000:8000 -d --rm --network lambda-local --name dynamodb -v $(CURDIR)/local/dynamodb:/data/ amazon/dynamodb-local -jar DynamoDBLocal.jar -sharedDb -dbPath /data

dockerstop stop:
	@ docker stop dynamodb

containerprune prune:
	@ docker container prune

clean:
	@ echo "Cleaning old files..."
	@ rm -rf .aws-sam
	@ rm -rf dist
	@ rm -rf build
	@ rm -rf **/__pycache__
	@ echo "All done!"

build:
	@ sam build --use-container

invoke:
	@ sam local invoke CMCEngineFunction --docker-network lambda-local

deploy:
	@ sam build --use-container
	@ sam deploy --guided

