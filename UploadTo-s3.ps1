[CmdletBinding()]
PARAM (
    [Parameter(Mandatory=$True)]
    [string]
    $AWS_ACCESS_KEY_ID,

    [Parameter(Mandatory=$True)]
    [string]
    $AWS_SECRET_ACCESS_KEY,

    [Parameter(Mandatory=$False)]
    [string]
    $AWS_SESSION_TOKEN,

    [Parameter(Mandatory=$True)]
    [string]
    $BucketBasePath,

    [Parameter(Mandatory=$False)]
    [string[]]
    $Files = @("ALL")
)

BEGIN {
    $Env:AWS_ACCESS_KEY_ID     = $AWS_ACCESS_KEY_ID
    $Env:AWS_SECRET_ACCESS_KEY = $AWS_SECRET_ACCESS_KEY
    if ( $PSBoundParameters.ContainsKey("AWS_SESSION_TOKEN") ) {
        $Env:AWS_SESSION_TOKEN     = $AWS_SESSION_TOKEN
    }

    if ( $BucketBasePath -match  "^s3:" ) {
        $UploadBasePath = $BucketBasePath
    }
    else {
        $UploadBasePath =  "s3://{0}" -f $BucketBasePath
    }
}

PROCESS {
    if ( $Files.length -eq 1 -and $Files[0] -eq "ALL" ) {
        $FileList = Get-ChildItem *.zip, *.yml -File
    }
    else { 
        $FileList = Get-ChildItem -File $Files
    }
    
    $FileList | ForEach-Object {
        $LocalFile = $_.Name
        $RemotePath = "{0}/{1}" -f [regex]::Replace($UploadBasePath,"/$",""), $LocalFile
        Write-Host "aws s3 cp $LocalFile $RemotePath"
        aws s3 cp  $LocalFile $RemotePath
    }
}