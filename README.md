# update-api-gateway-resources

A simple serverless application that will update your api gateway resources from a swagger file.  Keeping the API gateway updated and configured can be cumbersome - merge your existing API with updates to your API changes, and you can lose a lot of your previous configurations.  The included lambda function is designed to keep an eye on a S3 bucket, and when a swagger.json file is uploaded to a folder, it will look for a configuration file in the same directory, which defines what to do as a default with newly imported resources.  It then caches the configurations of existing resources, imports your swagger file, puts back any cached settings on pre-existing resources, and then applies the default configurations to new resources.



### update-api-gateway-resources.py
This is the code for the lambda function.

### api_config.json
This is a sample configuration json file.  This sits in the same directory where swagger.json is uploaded to.

When the lambda is triggered, it looks for this file in the same directory, and this is used to specify the default configuration for new resources.
The lambda is configured so that you can drop a swagger.json in any location, so different stages can be applied by having different folders configured with their own api_config.json.  For instance, you can have your bucket setup as follows:

```
/MyFirstApi/Stage 
/MyFirstApi/Prod 
/MySecondApi/Prod 
```

If you drop a swagger.json in /MyFirstApi/Stage, it will look for a file called /MyFirstApi/Stage/


### test-event.json
This is a sample of what the s3 trigger event would look like when you drop a swagger.json in the folder.  

### ps1 files
A couple helper files.
build-zips.ps1 will package any subdirectory in the current directory as a .zip.  This is for the purpose of packaging the update-api-gateway-resources.py into a zip that can be imported into Lambda.
``` powershell
./build-zips.ps1
```

UploadTo-s3.ps1 is pretty self explanatory, but will upload any .yml and .zip files to the specified s3 bucket/folder.  This is for the purpose of uploading your files for use by cloud formation, etc.

``` powershell
.\UploadTo-s3.ps1 -AWS_ACCESS_KEY_ID $Env:AWS_ACCESS_KEY_ID -AWS_SECRET_ACCESS_KEY $Env:AWS_SECRET_ACCESS_KEY -AWS_SESSION_TOKEN $Env:AWS_SESSION_TOKEN -BucketBasePath my-already-existing-bucket/folder/or/key
```

### Cloud formation template
TODO:  Just need to build out a template to build the solution - TBD
