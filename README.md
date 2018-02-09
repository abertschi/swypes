# Swypes

A (quick and dirty) python script to talk to tinder's servers

## Features
- auto like users around your location
- super like users based on their ethnicity (asian, white, black, hispanic filter)
- postpone likes/super likes to next day if no more quota
- prioritize postponed likes
- html export
- image download
- telegram bot

## Usage
```
$ python swypes.py --help
usage: swypes.py [-h] [--all] [--remove-pending REMOVE_PENDING]
                 [--super-like-user SUPER_LIKE_USER]
                 [--super-like-ethnicity SUPER_LIKE_ETHNICITY]
                 [--no-super-like NO_SUPER_LIKE] [--prioritize PRIORITIZE]
                 [--download-pictures] [--create-html CREATE_HTML]

optional arguments:
  -h, --help            show this help message and exit
  --all
  --remove-pending USER-ID
  --super-like-user USER-ID
  --super-like-ethnicity SUPER_LIKE_ETHNICITY
  --no-super-like USER-ID
  --prioritize USER-ID
  --download-pictures
  --create-html CREATE_HTML Create html with entries X days back

```
  

<img src="./html-export.png" width="900">
