Get-ChildItem -Directory | ForEach-Object {
    $ZipName = "{0}.zip" -f $_.Name
    Get-ChildItem -Path $_.FullName | Compress-Archive -DestinationPath $ZipName -force
}