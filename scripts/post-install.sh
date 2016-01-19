#!/bin/bash

update-rc.d xylem defaults
service xylem status >/dev/null 2>&1

if [ "$?" -gt "0" ];
then
    service xylem start 2>&1
else
    service xylem restart 2>&1
fi 

exit 0
