import os
import requests
import json

from .errors import *
import logging


class BaseAPI(object):
    """
    Base class for the pyfcm API wrapper for FCM
    """

    CONTENT_TYPE = "application/json"
    FCM_END_POINT = "https://fcm.googleapis.com/fcm/send"
    # FCM only allows up to 1000 reg ids per bulk message.
    FCM_MAX_RECIPIENTS = 1000

    #: Indicates that the push message should be sent with low priority. Low
    #: priority optimizes the client app's battery consumption, and should be used
    #: unless immediate delivery is required. For messages with low priority, the
    #: app may receive the message with unspecified delay.
    FCM_LOW_PRIORITY = 'normal'

    #: Indicates that the push message should be sent with a high priority. When a
    #: message is sent with high priority, it is sent immediately, and the app can
    #: wake a sleeping device and open a network connection to your server.
    FCM_HIGH_PRIORITY = 'high'

    def __init__(self, api_key=None, proxy_dict=None):
        """

        :type proxy_dict: dict, api_key: string
        """
        if api_key:
            self._FCM_API_KEY = api_key
        elif os.getenv('FCM_API_KEY', None):
            self._FCM_API_KEY = os.getenv('FCM_API_KEY', None)
        else:
            raise AuthenticationError("Please provide the api_key in the google-services.json file")
        self.FCM_REQ_PROXIES = None
        if proxy_dict and isinstance(proxy_dict, dict) and (('http' in proxy_dict) or ('https' in proxy_dict)):
            self.FCM_REQ_PROXIES = proxy_dict

    def request_headers(self):
        return {
            "Content-Type": self.CONTENT_TYPE,
            "Authorization": "key=" + self._FCM_API_KEY,
        }

    def parse_response(self, response):
        """
        Parses the json response sent back by the
        server and tries to get out the important return variables

        Returns a python dict of multicast_id(long), success(int), failure(int), canonical_ids(int), results(list)
        """
        if 'content-length' in response.headers and int(response.headers['content-length']) <= 0:
            return {}
        parsed_response = response.json()

        multicast_id = parsed_response.get('multicast_id', None)
        success = parsed_response.get('success', 0)
        failure = parsed_response.get('failure', 0)
        canonical_ids = parsed_response.get('canonical_ids', 0)
        results = parsed_response.get('results', [])
        message_id = parsed_response.get('message_id', None)  # for topic messages

        return {'multicast_id': multicast_id,
                'success': success,
                'failure': failure,
                'canonical_ids': canonical_ids,
                'results': results}

    def registration_id_chunks(self, registration_ids):
        try:
            xrange
        except NameError:
            xrange = range
        """Yield successive 1000-sized (max fcm recipients per request) chunks from registration_ids."""
        for i in xrange(0, len(registration_ids), self.FCM_MAX_RECIPIENTS):
            yield registration_ids[i:i + self.FCM_MAX_RECIPIENTS]

    def json_dumps(self, data):
        """Standardized json.dumps function with separators and sorted keys set."""
        return (json.dumps(data, separators=(',', ':'), sort_keys=True)
                .encode('utf8'))

    def parse_payload(self,
                      registration_ids=None,
                      topic_name=None,
                      message_body=None,
                      message_title=None,
                      message_icon=None,
                      sound=None,
                      condition=None,
                      collapse_key=None,
                      delay_while_idle=False,
                      time_to_live=None,
                      restricted_package_name=None,
                      low_priority=False,
                      dry_run=False,
                      data_message=None,
                      click_action=None,
                      badge=None,
                      color=None,
                      tag=None,
                      body_loc_key=None,
                      body_loc_args=None,
                      title_loc_key=None,
                      title_loc_args=None,
                      **extra_kwargs):

        """

        :rtype: json
        """
        fcm_payload = dict()
        if registration_ids:
            if len(registration_ids) > 1:
                fcm_payload['registration_ids'] = registration_ids
            else:
                fcm_payload['to'] = registration_ids[0]
        if condition:
            fcm_payload['condition'] = condition
        else:
            # In the `to` reference at: https://firebase.google.com/docs/cloud-messaging/http-server-ref#send-downstream
            # We have `Do not set this field (to) when sending to multiple topics`
            # Which is why it's in the `else` block since `condition` is used when multiple topics are being targeted
            if topic_name:
                fcm_payload['to'] = '/topics/%s' % (topic_name)
        if low_priority:
            fcm_payload['priority'] = self.FCM_LOW_PRIORITY
        else:
            fcm_payload['priority'] = self.FCM_HIGH_PRIORITY

        if delay_while_idle:
            fcm_payload['delay_while_idle'] = delay_while_idle
        if collapse_key:
            fcm_payload['collapse_key'] = collapse_key
        if time_to_live:
            if isinstance(time_to_live, int):
                fcm_payload['time_to_live'] = time_to_live
            else:
                raise InvalidDataError("Provided time_to_live is not an integer")
        if restricted_package_name:
            fcm_payload['restricted_package_name'] = restricted_package_name
        if dry_run:
            fcm_payload['dry_run'] = dry_run

        if data_message:
            if isinstance(data_message, dict):
                fcm_payload['data'] = data_message
            else:
                raise InvalidDataError("Provided data_message is in the wrong format")
        if message_body:
            fcm_payload['notification'] = {
                'body': message_body,
                'title': message_title,
                'icon': message_icon
            }
            if click_action:
                fcm_payload['notification']['click_action'] = click_action
            if badge:
                fcm_payload['notification']['badge'] = badge
            if color:
                fcm_payload['notification']['color'] = color
            if tag:
                fcm_payload['notification']['tag'] = tag
            if body_loc_key:
                fcm_payload['notification']['body_loc_key'] = body_loc_key
            if body_loc_args:
                fcm_payload['notification']['body_loc_args'] = body_loc_args
            if title_loc_key:
                fcm_payload['notification']['title_loc_key'] = title_loc_key
            if title_loc_args:
                fcm_payload['notification']['title_loc_args'] = title_loc_args
            # only add the 'sound' key if sound is not None
            # otherwise a default sound will play -- even with empty string args.
            if sound:
                fcm_payload['notification']['sound'] = sound

        else:
            # This is needed for iOS when we are sending only custom data messages
            fcm_payload['content_available'] = True

        if extra_kwargs:
            fcm_payload.update(extra_kwargs)

        return self.json_dumps(fcm_payload)

    def send_request(self, payloads=None):

        for payload in payloads:
            response = requests.post(self.FCM_END_POINT, headers=self.request_headers(), data=payload)
            if self.FCM_REQ_PROXIES:
                response = requests.post(self.FCM_END_POINT, headers=self.request_headers(), data=payload, proxies=self.FCM_REQ_PROXIES)
            if response.status_code == 200:
                return self.parse_response(response)
            elif response.status_code == 401:
                raise AuthenticationError("There was an error authenticating the sender account")
            elif response.status_code == 400:
                raise InternalPackageError(response.text)
            else:
                raise FCMServerError("FCM server is temporarily unavailable")
