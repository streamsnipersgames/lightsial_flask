# Some useful commands

[Docs how to create and deploy](https://aws.amazon.com/getting-started/hands-on/serve-a-flask-app/)

## Commands for deployment and create container

```bash

# build container
docker build -t flask-container .

# run container locally
docker run -p 5000:5000 flask-container 

# push container
aws lightsail push-container-image --region us-east-1 --service-name flask-service --label flask --image flask-container:latest

# get container
aws lightsail get-container-services --service-name flask-service

# deploy container
aws lightsail create-container-service-deployment --service-name flask-service --containers file://containers.json --public-endpoint file://public-endpoint.json
```

## Deployment steps:
- build container in current folder
- try container on local
- push container
- after pushing it'll tell u number update containers.json with new number
- deploy container 