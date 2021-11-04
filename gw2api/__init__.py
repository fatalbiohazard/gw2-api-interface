import copy

import requests
import pandas as pd
from requests.packages import urllib3

# mainly duplicates that are not needed
broken_notused_endpoints = ['account/home', 'account/mounts', 'pvp/seasons/:id/leaderboards/:board/:region', 'legendaryarmory',
                            'account/progression', 'commerce/exchange', 'emblem', 'home', 'mounts', 'pvp']


class GuildWars2Client:
    """Parent client that stores the API Objects and metadata"""

    lang = 'en'
    version = 'v2'
    base_url = 'https://api.guildwars2.com'

    def __init__(self, base_url=base_url, version=version, lang=lang, api_key=None, proxy=None, verify_ssl=True):

        assert version in ('v1', 'v2')
        assert lang in ('en', 'es', 'de', 'fr', 'ko', 'zh')

        self.lang = lang
        self.proxy = proxy
        self.api_key = api_key
        self.version = version
        self.base_url = base_url
        self.verify_ssl = verify_ssl

        if not self.verify_ssl:
            # Disable SSL Warnings in that case to avoid unnecessary verbosity
            urllib3.disable_warnings()

        GuildWars2Client.lang = lang
        GuildWars2Client.version = version
        GuildWars2Client.base_url = base_url

        # This must be done before we build and assign the API objects (below)
        #  so as to avoid initializing them with a null session
        self.session = self.__build_requests_session()
        self.objects = None

        # Constructs a list of API Objects to be assigned to this instance
        self.__build_object_clients()
        self.update_objects = self.check_endpoints()

    def __build_requests_session(self):
        """Build Request Session that handles all HTTP requests"""
        session = requests.Session()

        # Particularly useful then passing requests through a local proxy
        session.verify = self.verify_ssl

        session.headers.update(
            {'User-Agent': 'gw2-api-interface-python-wrapper', 'Accept': 'application/json', 'Accept-Language': GuildWars2Client.lang})

        if self.api_key:
            assert isinstance(self.api_key, str)
            session.headers.update({'Authorization': 'Bearer ' + self.api_key})

        if self.proxy:
            # If this hits, the proxy format should be:
            # {
            #    'http': HTTP_PROXY_HOST:PORT,
            #    'https': HTTPS_PROXY_HOST:PORT
            # }
            assert isinstance(self.proxy, dict)
            session.proxies = self.proxy

        return session

    def __build_object_clients(self):
        """Creates and assigned API Objects to the class instance"""
        if GuildWars2Client.version == 'v1':
            from gw2api.objects.api_version_1 import API_OBJECTS
        elif GuildWars2Client.version == 'v2':
            from gw2api.objects.api_version_2 import API_OBJECTS
        else:
            raise ValueError('Unable to import API Objects, make '
                             'sure the version passed is valid - ' + GuildWars2Client.version)

        objects = API_OBJECTS

        for object_ in objects:
            object_ = copy.copy(object_)
            object_.session = self.session
            setattr(self, object_.__class__.__name__.lower(), object_)
        self.objects = objects

    def check_endpoints(self):
        url = "https://api.guildwars2.com/v2.json?v=latest"
        json_data = requests.Session().get(url).json().get('routes')
        df = pd.DataFrame(json_data).convert_dtypes()
        df['object_type'] = df['path'].str.replace("/v2/", "")

        cur_objs = [obj.object_type for obj in self.objects]
        df2 = pd.DataFrame(data={"object_type": cur_objs})
        merge = df.merge(df2, how="outer", left_on='object_type', right_on='object_type', indicator=True).sort_values(by=['object_type'])
        merge = (
            merge[((merge['active'] == True) | (merge['_merge'] == "right_only")) & (merge['object_type'].isin(broken_notused_endpoints) != True)]
            .sort_values(by=['object_type'])
            .reindex(columns=['object_type', '_merge', 'auth'])
            .reset_index()
        )
        if len(merge[merge['_merge'] == "left_only"]) <= 0:
            return False
        return merge[merge['_merge'] == "left_only"]['object_type'].tolist()

    def __repr__(self):
        return f'<GuildWars2Client {self.base_url}\nVersion: {self.version}\nAPI Key: {self.api_key}\n' \
               f'Language: {self.lang}\nProxy: {self.proxy}\nVerify SSL?: {self.verify_ssl}>'
