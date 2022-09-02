import requests
import json
import os
import boto3
from botocore.exceptions import ClientError
import copy


def matchItems(obj1, obj2):
    first = orderedDict(copy.deepcopy(obj1))
    second = orderedDict(copy.deepcopy(obj2))
    return first == second

def orderedDict(obj):
    if isinstance(obj, dict):
        return sorted((k, orderedDict(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(orderedDict(x) for x in obj)
    else:
        return obj

def get_all_resources(client,apiid):
    all_resources = []
    resources = client.get_resources(
        restApiId=apiid,
        limit=500
    )
    #
    if len(resources['items']) > 0:
        all_resources.extend(resources['items'])
        #
    # make additional calls if pagination returns a next page token
    while 'position' in resources:
        resources = client.get_resources(
            restApiId=apiid,
            limit=500,
            position=resources['position']
        )
        if len(resources['items']) > 0:
            all_resources.extend(resources['items'])
    return all_resources

def get_api_config_current(awsregion, apiid):
    client = boto3.client('apigateway', awsregion)
    all_resources = get_all_resources(client, apiid)
    #
    for r in all_resources:
        if 'resourceMethods' not in r:
            continue
        for k in r['resourceMethods'].keys():
            method_response = client.get_method(
                restApiId=apiid,
                resourceId=r['id'],
                httpMethod=k
            )
            r['resourceMethods'][k]['config'] = method_response
    #
    return all_resources

def update_api_resources(awsregion, apiid, resources_before: list, baseUri, default_config):
    client = boto3.client('apigateway', awsregion)
    all_resources = get_all_resources(client,apiid)
    returnStatus = True
    for resource in all_resources:
        if 'resourceMethods' in resource:
            cached_config = [c for c in resources_before if c['path'] == resource['path']]
            
            if len(cached_config) != 1:
                cached_config = {}
            else:
                cached_config = cached_config[0]

            for method in resource['resourceMethods'].keys():
                current_method_config = resource['resourceMethods'][method]
                print(json.dumps(current_method_config))
                
                # These are the available properties to apply for each of these operations.  Any of these settings are valid
                # in the config.json
                integration_properties = ["type","uri","integrationHttpMethod","connectionType","passthroughBehavior","cacheKeyParameters","timeoutInMillis","connectionId","credentials","requestParameters","requestTemplates","cacheNamespace","contentHandling","tlsConfig"]
                auth_properties = ["authorizationType","apiKeyRequired","authorizerId","operationName","requestValidatorId","authorizationScopes"]
                putIntegration = False
                putAuth = False
                
                if 'resourceMethods' in cached_config and method in cached_config['resourceMethods']:
                    print("#### {} is cached".format(method))
                    cached_method_config = cached_config['resourceMethods'][method]
                    print(json.dumps(cached_method_config))
                    if 'config' in current_method_config and 'methodIntegration' in current_method_config['config']:
                        integration_matches = matchItems(cached_method_config['config']['methodIntegration'],current_method_config['config']['methodIntegration'])
                    else:
                        integration_matches = False
                    
                    if 'config' in current_method_config:
                        authorizationType_matches = matchItems(cached_method_config['config']['authorizationType'],current_method_config['config']['authorizationType'])
                        apiKeyRequired_matches = matchItems(cached_method_config['config']['apiKeyRequired'],current_method_config['config']['apiKeyRequired'])
                    else:
                        authorizationType_matches = False
                        apiKeyRequired_matches = False

                    if integration_matches and authorizationType_matches and apiKeyRequired_matches:
                        # the curent config matches the cached config
                        continue
                    
                    # We saved a copy of this configuration, so apply it.
                    auth_kwargs = {
                        "restApiId" : apiid,
                        "resourceId" : resource['id'],
                        "httpMethod" : method
                    }
                    # Loop over available keys and see what is cached, add it.
                    auth_patch = []
                    for k in auth_properties:
                        if k in cached_method_config['config']:
                            putAuth = True
                            auth_op = {
                                "op" : "replace",
                                "path" : "/{}".format(k),
                                "value" : str(default_config['DefaultAuthorization'][k])
                            }
                            auth_patch.append(auth_op)
                    
                    if (len(auth_patch) > 0 ):
                        auth_kwargs['patchOperations'] = auth_patch

                    integration_kwargs = {
                        "restApiId" : apiid,
                        "resourceId" : resource['id'],
                        "httpMethod" : method
                    }
                    # Loop over available keys and see what is cached, add it.   
                    for k in integration_properties:
                        if 'methodIntegration' in cached_method_config['config'] and k in cached_method_config['config']['methodIntegration']:
                            putIntegration = True
                            integration_kwargs[k] = cached_method_config['config']['methodIntegration'][k]
                    
                    if 'integrationHttpMethod' not in integration_kwargs:
                        integration_kwargs['integrationHttpMethod'] = integration_kwargs['httpMethod']
                    
                else:
                    # We don't have anything cached, so we will pull the defaults from the config file.
                    print("#### {} is NEW".format(method))
                    auth_kwargs = {
                        "restApiId" : apiid,
                        "resourceId" : resource['id'],
                        "httpMethod" : method 
                    }
                    auth_patch = []
                    for k in auth_properties:
                        if k in default_config['DefaultAuthorization']:
                            putAuth = True
                            auth_op = {
                                "op" : "replace",
                                "path" : "/{}".format(k),
                                "value" : str(default_config['DefaultAuthorization'][k])
                            }
                            auth_patch.append(auth_op)

                    if (len(auth_patch) > 0 ):
                        auth_kwargs['patchOperations'] = auth_patch

                    integration_kwargs = {
                        "restApiId" : apiid,
                        "resourceId" : resource['id'],
                        "httpMethod" : method,
                        "integrationHttpMethod" : method,
                        "uri" : "{}{}".format(baseUri, resource['path'])
                    }
                    for k in integration_properties:
                        if k in default_config['DefaultIntegration']:
                            putIntegration = True
                            integration_kwargs[k] = default_config['DefaultIntegration'][k]
                
                if putIntegration:
                    print(integration_kwargs)
                    try:
                        response = client.put_integration(**integration_kwargs)
                        print(response)
                    except ClientError as e:
                        print(e.response)
                        returnStatus = False
                    
            
                if putAuth:
                    print(auth_kwargs)
                    try:
                        response = client.update_method(**auth_kwargs)
                        print(response)
                    except ClientError as e:
                        print(e.response)
                        returnStatus = False
    return returnStatus
    
def update_api_endpoint(awsregion, apiid, mode, swaggerdefinition, parameters):
    client = boto3.client('apigateway', awsregion)

    api_response = client.put_rest_api(
        restApiId= apiid,
        mode=mode,
        failOnWarnings=True,
        parameters=parameters,
        body=swaggerdefinition
    )

    if api_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return True
    else:
        return False

def deploy_api_endpoint(awsregion, apiid, deploymentStage):
    client = boto3.client('apigateway', awsregion)
    print("deploying to {}".format(deploymentStage))
    deploy_response = client.create_deployment(
        restApiId=apiid,
        stageName=deploymentStage,
        stageDescription='Lambda automated deployment to {}'.format(deploymentStage),
        description='Lambda automated deployment to {}'.format(deploymentStage)
    )
    if deploy_response['ResponseMetadata']['HTTPStatusCode'] == 200 | deploy_response['ResponseMetadata']['HTTPStatusCode'] == 201:
        print("Deployment success!")
        return True
    else:
        return False

# Function to get the swagger definition json, updating with the replace_dictionary.
# can be configured to pull from the URL or to use existing json read from s3 file
def get_swagger_definition(swaggerUri, swaggerJson, replace_dictionary):
    if swaggerUri != None:
        response = requests.get(swaggerUri)
        if response.status_code == 200:
            swagger_raw = response.text
    elif swaggerJson != None:
        swagger_raw = swaggerJson
    else:
        return False

    for key in replace_dictionary.keys():
        swagger_raw = swagger_raw.replace(key,replace_dictionary[key])
    return swagger_raw

def get_s3_file_contents(bucketName, fileKey):
    s3 = boto3.client('s3')
    try:
        file = s3.get_object(Bucket = bucketName, Key = fileKey)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return False
        else:
            raise e
    body = file['Body']
    contents = body.read().decode('utf-8') 
    return contents

def copy_s3_item(sourceBucket, targetBucket, sourceKey, destinationKey):
    s3 = boto3.client('s3')
    # Copies object located in mybucket at sourceKey
    # to the location mybucket at destinationKey
    copy_source = {
        'Bucket': sourceBucket,
        'Key': sourceKey
    }
    try:
        s3.copy(copy_source, targetBucket, destinationKey)
    except ClientError as e:
        print(e.response)

# as of now unused.  Was intending to use this to get the VPC Id from the name
# but its just as easy to get the id and store in the config
def get_vpc_link(name, id=None):
    client = boto3.client('apigateway')
    if id != None:
        response = client.get_vpc_link(vpcLinkId=id)
        return response
    else:
        response = client.get_vpc_links()
    for link in response['items']:
        if link['name'] == name:
            return link

def lambda_handler(event, context):
    print(json.dumps(event))
    def_region = os.environ["DEFAULT_REGION"]
    def_mode = 'merge'
    def_parameters = {"endpointConfigurationTypes" : "REGIONAL"}

    if 'Records' in event.keys():
        for record in event['Records']:
            if record['eventSource'] != 'aws:s3':
                print("Record source is not S3, it is: {}".format(record['eventSource']))
                continue
            # Grab various variables from the payload of the event
            bucketName = record['s3']['bucket']['name']
            print("bucketName is {}".format(bucketName))
            
            key = record['s3']['object']['key']
            print("key is {}".format(key))
            
            arrParts = key.split("/")
            filename = arrParts[-1]
            print("filename is {}".format(filename))
            
            folder = "/".join(arrParts[0:len(arrParts)-1])
            print("folder is {}".format(folder))
            
            config_key = "/".join([folder,"api_config.json"])
            print(config_key)
            
            # load the api_config.json 
            config = json.loads(get_s3_file_contents(bucketName, config_key))
            if config == False:
                print("Config file not found - will be unable to configure defaults!!")
                config = {}

            uri = config['SwaggerUri']
            print(uri)

            # If the region is specified in the config.json, use the specified region, otherwise use
            # whatever the default is from the environment variable of the Lambda
            region = config.get('Region',def_region)
            endpointId = config.get('EndpointId',None)
            if endpointId is None:
                continue

            ### Start pulling values out of the imported config
            # Considering adding flag in config file so the swagger defintion is pulled live from a swagger URL
            # rather than just relying on the file in s3 (this was the original design where the lambda was triggered by SQS)
            swaggerUri = config.get('SwaggerUri',None)
            baseUri = config.get('ApiBaseUri',None)
            mode = config.get('ImportMode',def_mode)
            parameters = config.get('Parameters',def_parameters)
            replaceDictionary = config.get('StringReplaceDictionary',{})
            deploymentStages = config.get('DeploymentStages',None)
           
            swaggerjson = get_s3_file_contents(bucketName, key)
            swaggerjsonPreviousKey = "{}.last".format(key)
            swaggerjsonPrevious = get_s3_file_contents(bucketName, swaggerjsonPreviousKey)


            if matchItems(swaggerjsonPrevious,swaggerjson):
                print("File for import matches previous import.  Skipping.")
                continue

            if swaggerUri and (swaggerjson == None or swaggerjson == "" or swaggerjson == "{}"):
                swaggerdefinition = get_swagger_definition(swaggerUri, None, replaceDictionary)
            elif swaggerjson != None or swaggerjson != "" or swaggerjson != "{}":
                swaggerdefinition = get_swagger_definition(None, swaggerjson, replaceDictionary)
            else:
                print('no swagger definition defined')

            # Get the current Definition of the API
            resources_before = get_api_config_current(region, endpointId)
            """ resources_before[1]['resourceMethods']['POST']['config']
            {
                "ResponseMetadata": {
                    "RequestId": "some guid",
                    "HTTPStatusCode": 200,
                    "HTTPHeaders": {
                        "date": "Tue, 26 Jul 9999 19: 31: 50 GMT", "content-type": "application/json", "content-length": "864", "connection": "keep-alive", "x-amzn-requestid": "Guid", "x-amz-apigw-id": "idstring"
                    },
                    "RetryAttempts": 0
                },
                "httpMethod": "POST",
                "authorizationType": "AWS_IAM",   ####  This is what we will use to import the authorization
                "apiKeyRequired": False,          ####  This is what we will use to import the authorization
                "requestParameters": {
                    "method.request.path.version": True
                },
                "requestModels": {
                    "application/*+json": "MyApiModel",
                    "application/json": "MyApiModel",
                    "text/json": "MyApiModel"
                },
                "methodResponses": {
                    "200": {
                        "statusCode": "200",
                        "responseModels": {
                            "application/json": "MyApiModel",
                            "text/json": "MyApiModel",
                            "text/plain": "MyApiModel"
                        }
                    }
                },
                "methodIntegration": {    ####  This is what we will use to import the integration
                    "type": "HTTP_PROXY",
                    "httpMethod": "POST",
                    "uri": "https://SomeApiTo.com/api/ProxyRequestTo",
                    "connectionType": "VPC_LINK",
                    "connectionId": "abcdefg",
                    "passthroughBehavior": "WHEN_NO_MATCH",
                    "timeoutInMillis": 29000,
                    "cacheNamespace": "hijkl",
                    "cacheKeyParameters": [],
                    "integrationResponses": {
                        "200": {
                            "statusCode": "200",
                            "responseTemplates": {}
                        }
                    }
                }
            } 
            """

            # Do the base import of the swagger to the API -> Returns True (success) or False (error)
            update_result = update_api_endpoint(region, endpointId, mode, swaggerdefinition, parameters)

            # If it returned True, now we need to update all the resources
            if update_result:
                update_resource_result = update_api_resources(region, endpointId, resources_before, baseUri, config)

            if update_result and update_resource_result:
                copy_s3_item(bucketName, bucketName, key, swaggerjsonPreviousKey)
                
            # If stages are specified for deployment, deploy to each specified stage
            if update_resource_result and deploymentStages != None:
                for stage in deploymentStages:
                    deploy_api_endpoint(region, endpointId, stage)
                
    else:
        print("no record in event keys")
        