#!/bin/bash

update-rc.d docker-xylem defaults
service docker-xylem status >/dev/null 2>&1

if [ "$?" -gt "0" ];
then
    service docker-xylem start 2>&1
else
    service docker-xylem restart 2>&1
fi 

exit 0
