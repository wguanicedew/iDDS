#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2019


"""
Base rest client to access IDDS system.
"""


import logging
import json
import requests
try:
    # Python 2
    from urllib import urlencode, quote
except ImportError:
    # Python 3
    from urllib.parse import urlencode, quote

from idds.common import exceptions
from idds.common.constants import HTTP_STATUS_CODE


class BaseRestClient(object):

    """Base Rest client"""

    def __init__(self, host=None, client_proxy=None, timeout=None):
        """
        Constructor of the BaseRestClient.

        :param host: the address of the IDDS server.
        :param client_proxy: the client certificate proxy.
        :param timeout: timeout in seconds.
        """

        self.host = host
        self.client_proxy = client_proxy
        self.timeout = timeout
        self.session = requests.session()
        self.retries = 2

    def build_url(self, url, path=None, params=None, doseq=False):
        """
        Build url path.

        :param url: base url path.
        :param path: relative url path.
        :param params: parameters to be sent with url.

        :returns: full url path.
        """
        full_url = url
        if path is not None:
            full_url = '/'.join([full_url, path])
        if params:
            full_url += "?"
            if isinstance(params, str):
                full_url += quote(params)
            else:
                full_url += urlencode(params, doseq=doseq)
        return full_url

    def get_request_response(self, url, type='GET', data=None, headers=None):
        """
        Send request to the IDDS server and get the response.

        :param url: http url to connection.
        :param type: request type(GET, PUT, POST, DEL).
        :param data: data to be sent to the IDDS server.
        :param headers: http headers.

        :returns: response data as json.
        :raises:
        """

        result = None

        for retry in range(self.retries):
            try:
                if type == 'GET':
                    result = self.session.get(url, timeout=self.timeout, headers=headers, verify=False)
                elif type == 'PUT':
                    result = self.session.put(url, data=json.dumps(data), timeout=self.timeout, headers=headers, verify=False)
                elif type == 'POST':
                    result = self.session.post(url, data=json.dumps(data), timeout=self.timeout, headers=headers, verify=False)
                elif type == 'DEL':
                    result = self.session.delete(url, data=json.dumps(data), timeout=self.timeout, headers=headers, verify=False)
                else:
                    return
            except requests.exceptions.ConnectionError as error:
                logging.warning('ConnectionError: ' + str(error))
                if retry >= self.retries - 1:
                    raise exceptions.ConnectionException('ConnectionError: ' + str(error))

            if result is not None:
                if result.status_code == HTTP_STATUS_CODE.OK:
                    if result.text:
                        return json.loads(result.text)
                    else:
                        return None
                else:
                    try:
                        if result.headers and 'ExceptionClass' in result.headers:
                            cls = getattr(exceptions, result.headers['ExceptionClass'])
                            msg = result.headers['ExceptionMessage']
                            raise cls(msg)
                        else:
                            if result.text:
                                data = json.loads(result.text)
                                raise exceptions.IDDSException(**data)
                            else:
                                raise exceptions.IDDSException('Unknown errors: no results returned')
                    except AttributeError:
                        raise exceptions.IDDSException(**data)
        if result is None:
            raise exceptions.IDDSException('Response is None')
