#!/bin/sh

unzip cpower-master.zip

if [ -d "custom_workflow" ]; then
  mv ./custom_workflow/config.py ./cpower-master
fi
rm -r custom_workflow
mv cpower-master custom_workflow
cd custom_workflow
chmod +x *.py
