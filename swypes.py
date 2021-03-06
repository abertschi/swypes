import requests
import json
import datetime
from tinydb import TinyDB, Query
import access_token
import enc
import sys
import argparse
import urllib
import os
from datetime import datetime, timedelta, time
from telegram.ext import Updater, CommandHandler
import signal
import telegram
import numpy as np

import logging

USE_FACE_REQ = False
FACE_REQ_HEADERS = {
    'app_id': '',
    'app_key': ''
}
FACEBOOK_ID = ''
FACEBOOK_USERNAME = ''
FACEBOOK_PASSWORD = ''
ENC_KEY = ''
FACEBOOK_TOKEN = ''

USE_TELEGRAM = False
USE_TELEGRAM_SUPER = True

TELEGRAM_BOT_SUPER_TOKEN = ''
TELEGRAM_BOT_LIKE_TOKEN = ''

CHAT_ID = ''

DATABASE = 'swypes.json'
HTML_EXPORT = 'swypes.html'

try:
    from credentials import *
except ImportError:
    pass


class Ethnicity:
    ASIAN = 'asian'
    BLACK = 'black'
    WHITE = 'white'
    HISPANIC = 'hispanic'
    OTHER = 'other'


class Gender:
    MALE = 'male'
    FEMALE = 'female'


class FaceMeta:
    def __init__(self, meta):
        self.ethnicity = Ethnicity.OTHER
        self.ethnicity_certainty = 0
        self.meta = meta
        self.gender = None
        self.is_valid = False
        self.age = None
        self.glasses = False

        if 'images' in meta and meta['images']:
            for image in meta['images']:
                if 'faces' in image:
                    for face in image['faces']:
                        if face['attributes']:
                            atts = face['attributes']
                            if atts['gender']['type'] == 'F':
                                self.gender = Gender.FEMALE
                            else:
                                self.gender = Gender.MALE

                            if 'age' in atts:
                                self.age = atts['age']

                            if 'glasses' in atts:
                                self.glasses = atts['glasses']

                            max_val = 0
                            max_key = ''
                            for ethnic in ['asian', 'white', 'black', 'other', 'hispanic']:

                                if atts[ethnic] > max_val:
                                    max_key = ethnic
                                    max_val = atts[ethnic]

                            switcher = {
                                'asian': Ethnicity.ASIAN,
                                'white': Ethnicity.WHITE,
                                'black': Ethnicity.BLACK,
                                'hispanic': Ethnicity.HISPANIC
                            }

                            self.ethnicity = switcher.get(max_key, Ethnicity.OTHER)
                            self.ethnicity_certainty = max_val
                            self.is_valid = True
                            break

    @staticmethod
    def get_face_meta(image_url):
        endpoint = 'https://api.kairos.com/detect'
        payload = {
            'selector': 'ROLL',
            'image': image_url
        }
        resp = requests.post(endpoint, headers=FACE_REQ_HEADERS, json=payload)
        if resp.status_code == 200:
            return FaceMeta(resp.json())
        else:
            raise Exception('No valid face meta data for ' + image_url)

    def to_json(self):
        if self.is_valid:
            return {
                'ethnicity': self.ethnicity,
                'ethnicity_certainty': self.ethnicity_certainty,
                'gender': self.gender,
                'is_valid': self.is_valid,
                'age': self.age,
                'glasses': self.glasses,
            }
        else:
            return {
                'is_valid': self.is_valid
            }


class TinderWrapper:
    def __init__(self):
        self.token = 'not-fetched'

    def fetch_token(self, token, id):
        self.token = self.get_api_token(token, id)

    def get_tinder_req_headers(self):
        return {
            'X-Auth-Token': self.token,
            'Content-type': 'application/json',
            'User-agent': 'Tinder/3.0.4 (iPhone; iOS 7.1; Scale/2.00)'
        }

    @staticmethod
    def get_api_token(token, id):
        url = 'https://api.gotinder.com/auth'
        body = {
            'facebook_token': token,
            'facebook_id': id
        }
        resp = requests.post(url, body)
        if resp.status_code != 200:
            raise Exception('can not auth with facebook creds: ' + resp.text)

        return resp.json().get('token')

    def get_location(self):
        resp = requests.get('https://api.gotinder.com/profile', headers=self.get_tinder_req_headers())
        if not resp.status_code == 200:
            raise Exception('can not get base location: ' + resp.text)
        else:
            data = resp.json()

            lat = None
            lon = None

            pos = data.get('pos')
            if pos:
                lon = pos.get('lon')
                lat = pos.get('lat')

            city = ''
            country = ''

            if data.get('pos_info') and \
                    data.get('pos_info').get('city') and \
                    data.get('pos_info').get('city').get('name'):
                city = data.get('pos_info').get('city').get('name')

            if data.get('pos_info') and \
                    data.get('pos_info').get('country') and \
                    data.get('pos_info').get('country').get('name'):
                country = data.get('pos_info').get('country').get('name')

            return {
                'lon': lon,
                'lat': lat,
                'city': city,
                'country': country
            }

    def get_recs(self):
        base_location = self.get_location()
        if not base_location:
            raise Exception('can not fetch base location')

        endpoint = 'https://api.gotinder.com/user/recs'
        resp = requests.get(endpoint, headers=self.get_tinder_req_headers())

        recs = []
        json_resp = resp.json()
        if resp.status_code == 200 and json_resp.get('status') == 200:
            for rec in json_resp.get('results'):

                pictures = []
                pictures_small = []
                schools = []
                jobs = []
                insta = ''

                for image in rec['photos']:
                    pictures.append(image['url'])
                    # for process_files in rec.get('processedFiles'):
                    #     if process_files.get('width') == 640:
                    #         pictures_small.append(process_files['url'])

                for school in rec.get('schools'):
                    schools.append(school.get('name'))
                if 'instagram' in rec:
                    insta = rec['instagram'].get('username')
                for job in rec.get('jobs'):
                    if 'company' in job:
                        jobs.append(job['company'].get('name'))

                recs.append({
                    'id': rec.get('_id'),
                    'base_location': base_location,
                    'distance_mi': rec.get('distance_mi'),
                    'bio': rec.get('bio'),
                    'name': rec.get('name'),
                    'gender': rec.get('gender'),
                    'birthdate': rec.get('birth_date'),
                    'ping_time': rec.get('ping_time'),
                    'photos': pictures,
                    'photos_small': pictures_small,
                    'insta': insta,
                    'jobs': jobs,
                    'schools': schools
                })
        else:
            if resp.json().get('message') not in ['recs timeout', 'recs exhausted']:
                raise Exception("problem with tinder api. cant fetch recs. " + json.dumps(resp.json()))
        return recs

    def like_user(self, user):
        resp = requests.get(f'https://api.gotinder.com/like/{user["id"]}', headers=self.get_tinder_req_headers())
        if resp.status_code != 200:
            msg = json.dumps(resp.json())
            raise Exception(f'not able to like user {Swypes.pretty_format_user(user)} {msg}')
        return resp.json()

    def super_like_user(self, user):
        resp = requests.post(f'https://api.gotinder.com/like/{user["id"]}/super', headers=self.get_tinder_req_headers())
        if resp.status_code != 200:
            msg = json.dumps(resp.json())
            raise Exception(f'not able to super like user {Swypes.pretty_format_user(user)} {msg}')
        return resp.json()


class Storage:
    def __init__(self):
        self.db = TinyDB(DATABASE)
        self.users = self.db.table('user')
        self.again = self.db.table('again')
        self.again_super = self.db.table('again_super')
        self.User_query = Query()
        self.Again_query = Query()
        self.Again_super_query = Query()

    def mark_user_as_to_be_liked(self, user):
        self.again.insert(user)

    def mark_user_as_liked(self, user):
        self.again.remove(self.Again_query.id == user['id'])
        self.store_user(user)

    def mark_user_as_super_liked(self, user):
        self.again_super.remove(self.Again_super_query.id == user['id'])
        user['liked'] = 'super'
        self.store_user(user)

    def mark_user_as_to_be_super_liked(self, user, user_id=None):
        to_like = user
        if user_id:
            to_like = self.get_user(user_id)

        to_like['liked'] = 'super'
        self.again_super.insert(to_like)

    def store_user(self, user):
        self.users.insert(user)
        print(f'saving {Swypes.pretty_format_user(user)}')

    def remove_pending(self, user_id):
        self.again_super.remove(self.Again_super_query.id == user_id)
        self.again.remove(self.Again_query.id == user_id)

    def get_user(self, user_id):
        user = self.users.search(self.User_query.id == user_id)
        if not user:
            raise Exception('user not found with userid: ' + user_id)
        else:
            return user[0]

    def is_super_like_pending(self, user_id):
        user = self.again_super.search(self.Again_super_query.id == user_id)
        return True if user else False

    def is_normal_like_pending(self, user_id):
        user = self.again.search(self.Again_query.id == user_id)
        return True if user else False

    def prioritize_super_pending(self, user_id):
        user = self.again_super.search(self.Again_super_query.id == user_id)
        if not user:
            raise Exception('user: ' + user_id + ' not found in super pending')

        max_prio = 0
        for user in self.again_super.all():
            prio = user.get('match_prio')
            if prio and prio > max_prio:
                max_prio = prio

        max_prio = max_prio + 1
        self.again_super.update({'match_prio': max_prio}, self.Again_super_query.id == user_id)

    def get_pending_super_likes_by_match_prio(self):
        return Swypes.sorted_by_match_prio_and_fifo(self.again_super.all())
        #return sorted(self.again_super.all(), reverse=True, key=lambda u: u.get('match_prio') if
        #u.get('match_prio') else 0)

    def get_pending_likes_by_match_prio(self):
        return Swypes.sorted_by_match_prio_and_fifo(self.again.all())
        #return sorted(self.again.all(), reverse=True, key=lambda u: u.get('match_prio') if
        #u.get('match_prio') else 0)

class Swypes:
    def __init__(self):
        self.tinder = TinderWrapper()
        self.storage = Storage()
        self.preference_for_super_like = 'asian'

    def super_like_user(self, user, store_on_failure=True, superBot=None):
        success = True
        user['liked'] = 'super'
        print(f'super liking {Swypes.pretty_format_user(user)}')

        super_like = self.tinder.super_like_user(user)
        if super_like.get('limit_exceeded'):
            print('Limit exceeded for super likes ' + Swypes.pretty_format_user(user))

            self.normal_like_user(user, False)
            success = False
            if store_on_failure:
                if superBot:
                    superBot.msg_pending(user)
                self.storage.mark_user_as_to_be_super_liked(user)

        return success

    def normal_like_user(self, user, store_on_failure=True):
        success = True
        user['liked'] = 'like'
        match_data = self.tinder.like_user(user)
        if match_data and match_data.get('match') is not None and match_data['match'] == True:
            print('New match on tinder: ' + Swypes.pretty_format_user(user))

        if match_data.get('limit_exceeded'):
            print('Limit exceeded for likes ' + Swypes.pretty_format_user(user))
            if store_on_failure:
                self.storage.mark_user_as_to_be_liked(user)
            success = False

        return success

    @staticmethod
    def sorted_by_match_prio_and_fifo(users):
        prio = [u for u in users if u.get('match_prio')]
        prio = sorted(prio, reverse=True, key=lambda u: u.get('match_prio') if u.get('match_prio') else 0)
        no_prio = [u for u in users if not u.get('match_prio')]
        no_prio = sorted(no_prio, reverse=True, key=lambda u: u.get('fetch') if u.get('fetch') else 0)
        return np.append(prio, no_prio)

    def match_pending_users(self, do_super_like, superBot=None):
        successful_super = []
        successful_normal = []
        pending = self.sorted_by_match_prio_and_fifo(self.storage.again.all())

        for user in pending:
            success = self.normal_like_user(user)
            if not success: break
            self.storage.mark_user_as_liked(user)
            successful_normal.append(user)

        pending_super = self.sorted_by_match_prio_and_fifo(self.storage.again_super.all())

        for user in pending_super:
            if do_super_like:
                success = self.super_like_user(user, store_on_failure=False)
            else:
                success = self.normal_like_user(user, store_on_failure=False)

            if not success: break
            self.storage.mark_user_as_super_liked(user)
            successful_super.append(user)

        return successful_normal, successful_super

    def rate_recommodations(self, recs, use_super_like=False, bot=None, superBot=None):
        stats_liked = []

        for rec in recs:
            meta = FaceMeta.get_face_meta(rec['photos'][0])
            user = rec
            user['meta'] = meta.to_json()
            user['fetch'] = str(datetime.now().date())

            if user['gender'] == 1 and user['meta'].get('gender') == 'female':
                success = True

                if meta.ethnicity == self.preference_for_super_like and use_super_like:
                    success = self.super_like_user(user, superBot=superBot)
                    if success:
                        stats_liked.append(user)
                else:
                    success = self.normal_like_user(user)
                    if success:
                        stats_liked.append(user)
                if success:
                    self.storage.store_user(user)
        return stats_liked

    def download_pictures(self):
        dir = './pictures'
        dir = os.path.abspath(dir)
        if not os.path.exists(dir):
            os.makedirs(dir)

        @staticmethod
        def download(users):
            for user in users:
                for photo in user['photos']:
                    url = photo
                    parts = url.split('/')
                    photoname = parts[len(parts) - 1]
                    try:
                        filename = user['id'] + '_' + photoname
                        path = dir + '/' + filename
                        if os.path.isfile(path):
                            print('skipping because exists: ' + path)
                            continue

                        request = urllib.request.Request(url, None)  # The assembled request
                        img = urllib.request.urlopen(request)

                        f = open(path, 'wb')
                        f.write(img.read())
                        f.close()
                        print('downloaded ' + path)

                    except Exception as e:
                        print(e)

        download(self.storage.users.get())
        download(self.storage.again.get())
        download(self.storage.again_super.get())

    def create_html(self, dateFrom=None):
        def create_user_profile(user):
            def encode(s):
                return str(s.encode("ascii", "xmlcharrefreplace"))

            pics = '<br/>'
            url = user["photos"][0]
            for pic in user['photos']:
                pics += f'<a href="{pic}"><img width="300px" src="{pic}" /></a>'

            data = f'<h1>{user["name"]}</h1>'
            del user['photos']
            data += json.dumps(user)

            data = data.replace(",", "<br/>")

            data += pics
            data = encode(data)
            data = data.replace("\"", "'")
            data = data.strip()
            data = data.replace('\n', '')

            # splits = url.split('/')
            # filename = splits[len(splits) - 1]
            # filename = '640x640_' + filename
            # splits[len(splits) - 1] = filename
            #
            # url = "/".join(splits)

            img = f'<a href="data:text/html,{data}"' \
                  f'><img width="200px" src="{url}" /></a> \n'
            return img

        def filter_user_by_date(users, date=None):
            if date:
                return [u for u in users if u.get('fetch') and str(u.get('fetch')) > str(date.date())]
            else:
                return users

        content = f'<html><body><h1>{self.preference_for_super_like}</h1>'
        alt = '<h1>Likes</h1>'

        for user in filter_user_by_date(self.storage.users.all(), dateFrom):
            profile = create_user_profile(user)
            if user['meta']['ethnicity'] == self.preference_for_super_like:
                content += profile
            else:
                alt += profile
        content = content + alt
        content += '<h1>pending super like</h1>'

        for pending_super in filter_user_by_date(self.storage.get_pending_super_likes_by_match_prio(), dateFrom):
            content += create_user_profile(pending_super)

        content += '<h1>pending like</h1>'
        for pending_like in filter_user_by_date(self.storage.get_pending_likes_by_match_prio(), dateFrom):
            content += create_user_profile(pending_like)

        file_prefix = HTML_EXPORT
        if dateFrom:
            file_prefix = file_prefix + str(dateFrom.date()) + ".html"

        text_file = open(file_prefix, "w+")
        text_file.write(content)

    @staticmethod
    def pretty_format_user(user):
        return f'{user["id"]}: {user["name"]} ({user["meta"].get("ethnicity")}) ({user["birthdate"]}) {user["photos"][0]}'


class Bot:
    def __init__(self, token, chat_id):
        self.chat_id = chat_id
        self.bot = telegram.Bot(token=token)

        self.updater = Updater(token)
        self.updater.dispatcher.add_handler(CommandHandler('hello', self.hello))

        self.updater.start_polling()

    def idle(self):
        self.updater.idle()

    def hello(self, bot, update):
        update.message.reply_text(
            'Hello {}'.format(update.message.chat_id))

    def send(self):
        self.bot.send_message(chat_id=self.chat_id, text="I'm sorry Dave I'm afraid I can't do that.")

    def msg(self, user):
        schools = ''
        for s in user['schools']:
            schools = schools + ' ' + s

        msg = '{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}' \
            .format(user["id"],
                    user["name"],
                    user['birthdate'],
                    'schools: ' + schools,
                    'fetched: ' + user["fetch"],
                    'status: ' + user.get('liked'),
                    user["meta"].get("ethnicity"),
                    user["bio"],
                    user['photos'][0])
        self.bot.send_message(chat_id=CHAT_ID,
                              text=msg)


class SuperBot:
    def __init__(self, token, chat_id):
        self.chat_id = chat_id
        self.bot = telegram.Bot(token=token)

    def idle(self):
        self.updater.idle()

    def send(self):
        self.bot.send_message(chat_id=self.chat_id, text="I'm sorry Dave I'm afraid I can't do that.")

    def msg(self, user, add_info=''):
        photos = ''
        for p in user['photos']:
            photos = photos + '\n' + p

        schools = ''
        for s in user['schools']:
            schools = schools + ' ' + s

        msg = '{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}' \
            .format(add_info,
                    user["id"],
                    user["name"],
                    user['birthdate'],
                    'schools: ' + schools,
                    'fetched: ' + user["fetch"],
                    'status: ' + user.get('liked'),
                    user["bio"],
                    user["meta"].get("ethnicity"),
                    photos)

        self.bot.send_message(chat_id=CHAT_ID,
                              text=msg)

    def msg_pending(self, user):
        self.msg(user, 'pending_user')


if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser()

    parser.add_argument('--all', action='store_true', default=False)  # loop until no more users
    parser.add_argument('--remove-pending')
    parser.add_argument('--super-like-user')
    parser.add_argument('--super-like-ethnicity', default='asian')
    parser.add_argument('--no-super-like', default=False)
    parser.add_argument('--prioritize')
    parser.add_argument('--download-pictures', default=False, action='store_true')
    parser.add_argument('--create-html', default=False, type=int, help="Create html with entries X numbers back",
                        )

    args = parser.parse_args()

    swypes = Swypes()
    swypes.create_html()

    if args.remove_pending:
        swypes.storage.remove_pending(str(args.remove_pending))
        print(f'Remvoing user {args.remove_pending} from pending like/super like')
        swypes.create_html()
        exit(0)

    if args.download_pictures:
        print('downloading pictures')
        swypes.download_pictures()
        exit(0)

    if args.prioritize:
        print(f'Prioritizing user {args.prioritize} in pending user users')
        swypes.storage.prioritize_super_pending(str(args.prioritize))
        swypes.create_html()
        exit(0)

    if args.super_like_user:
        swypes.storage.mark_user_as_to_be_super_liked(user=None, user_id=str(args.super_like_user))
        print('Super liking user in next run: ' + args.super_like_user)
        swypes.create_html()
        exit(0)

    if args.create_html:
        d = datetime.today() - timedelta(days=args.create_html)
        print("Generating html export with users fetched until " + str(d))
        swypes.create_html(dateFrom=d)
        exit(0)

    bot = None
    if USE_TELEGRAM:
        bot = Bot(token=TELEGRAM_BOT_LIKE_TOKEN, chat_id=CHAT_ID)

    superBot = None
    if USE_TELEGRAM_SUPER:
        superBot = SuperBot(token=TELEGRAM_BOT_SUPER_TOKEN, chat_id=CHAT_ID)

    if FACEBOOK_USERNAME and FACEBOOK_PASSWORD:
        print('fetching fb token')
        username = enc.decode(ENC_KEY, FACEBOOK_USERNAME)
        password = enc.decode(ENC_KEY, FACEBOOK_PASSWORD)
        FACEBOOK_TOKEN = access_token.get_access_token(username, password)

    swypes.tinder.fetch_token(FACEBOOK_TOKEN, FACEBOOK_ID)
    swypes.preference_for_super_like = args.super_like_ethnicity
    print('matching pending users... ')
    normal_liked, super_liked = swypes.match_pending_users(do_super_like=not args.no_super_like, superBot=superBot)

    fetch_again = True
    stats = []

    while fetch_again:
        print('fetching new recs ...')
        recs = swypes.tinder.get_recs()
        print('fetched ' + str(len(recs)) + ' recs')

        if not args.all:
            fetch_again = False
        if not recs:
            print('no new recommondations available')
            fetch_again = False

        stats_liked = swypes.rate_recommodations(recs, use_super_like=not args.no_super_like, superBot=superBot)
        if stats_liked:
            stats.extend(stats_liked)
        else:
            fetch_again = False

    swypes.create_html()


    def notify_chat(user):
        if bot:
            bot.msg(user)


    def notify_super_chat(user):
        if superBot:
            superBot.msg(user)


    print('\n\n ==== stats: =====\n')
    print('liked: ')
    for user in [u for u in stats if u['liked'] == 'like']:
        print(Swypes.pretty_format_user(user))
        notify_chat(user)

    for u in normal_liked:
        print(Swypes.pretty_format_user(u))
        notify_chat(u)

    print('super liked: ')
    for user in [u for u in stats if u['liked'] == 'super']:
        print(Swypes.pretty_format_user(user))
        notify_super_chat(user)

    for u in super_liked:
        print(Swypes.pretty_format_user(u))
        notify_super_chat(u)

    print('killing script')
    os.kill(os.getpid(), signal.SIGKILL)
    exit(0)
    print('this should not happen')
